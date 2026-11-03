"""The daily run for one feed: fetch sources, keep what is new, build documents, triage, rank.

Idempotent: every handled URL goes into the seen-set, so a second run only touches new items. Transient failures
(network errors, LLM errors) are NOT marked seen and are retried next run; deliberate skips (paywalled, robots,
too short) are marked seen so they are not retried every day.
"""
import difflib
import hashlib
import json
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from newsletter_brief.config import settings
from newsletter_brief.db.store import Store
from newsletter_brief.parse.canonicalize import canonicalize
from newsletter_brief.schemas import Document, TriageItem
from newsletter_brief.sources.article import ensure_full_text
from newsletter_brief.sources.registry import Source, by_feed
from newsletter_brief.sources.rss import FeedEntry, entry_to_document, fetch_entries
from newsletter_brief.sources.sitemap import fetch_sitemap_entries
from newsletter_brief.summarize.backend import LLMError
from newsletter_brief.summarize.checks import unverified_numbers
from newsletter_brief.summarize.extract import triage_document

CONFIDENCE_RANK = {"high": 2, "medium": 1, "low": 0}
TRANSIENT = {"blocked", "error"}  # retried next run; everything else is a final decision


def url_key(url: str) -> str:
    return hashlib.sha1(canonicalize(url).encode()).hexdigest()[:16]


@dataclass
class FeedItem:
    item: TriageItem
    source: Source
    published: datetime | None
    unverified: list[str]
    duplicate_of: str | None = None


@dataclass
class Report:
    feed: str
    days: int
    sources_ok: int = 0
    feed_errors: list[tuple[str, str]] = field(default_factory=list)
    entries_in_window: int = 0
    already_seen: int = 0
    over_cap: int = 0
    updated: int = 0  # watched pages whose text really changed and were triaged again
    skipped: Counter = field(default_factory=Counter)
    llm_errors: list[tuple[str, str]] = field(default_factory=list)
    items: list[FeedItem] = field(default_factory=list)
    seconds: float = 0.0
    usage: dict = field(default_factory=dict)

    def ranked(self) -> list[FeedItem]:
        return sorted(self.items, key=lambda f: (-f.item.relevance, -CONFIDENCE_RANK[f.item.confidence],
                                                 -(f.published.timestamp() if f.published else 0)))


def _usage_since(offset: int) -> dict:
    if not settings.usage_log.exists():
        return {}
    with settings.usage_log.open("rb") as f:
        f.seek(offset)
        rows = [json.loads(l) for l in f.read().decode("utf-8").splitlines() if l.strip()]
    return {"calls": len(rows), "output_tokens": sum(r.get("output_tokens") or 0 for r in rows),
            "cost_usd": round(sum(r.get("cost_usd") or 0 for r in rows), 4)}


def _page_changed(store: Store, entry: FeedEntry) -> bool:
    """A watched (sitemap) page is worth a look when it was never handled, or its lastmod moved past the one we recorded.
    A page with no lastmod can only be new, never updated."""
    key = url_key(entry.link)
    state = store.page_state(key)
    if state is None:
        return not store.seen(key)
    if entry.date is None or not state["lastmod"]:
        return False
    return entry.date > datetime.fromisoformat(state["lastmod"])


def run_feed(
    feed: str = "engineering", days: int = 3, per_source_cap: int = 5, max_docs: int = 60, *,
    refresh: bool = False, store: Store | None = None, sources: list[Source] | None = None, now: datetime | None = None,
    fetch: Callable[[str], list[FeedEntry]] = fetch_entries,
    fetch_sitemap: Callable[[Source, Store, datetime], list[FeedEntry]] = fetch_sitemap_entries,
    ensure: Callable[[Document], tuple[Document | None, str]] = ensure_full_text,
    triage: Callable[[Document], TriageItem | None] = triage_document,
    log: Callable[[str], None] = print,
) -> Report:
    store = store or Store()
    now = now or datetime.now(timezone.utc)
    report = Report(feed=feed, days=days)
    usage_offset = settings.usage_log.stat().st_size if settings.usage_log.exists() else 0
    t0 = time.time()
    cutoff = now - timedelta(days=days)

    candidates: list[tuple[Source, FeedEntry]] = []
    for src in (sources if sources is not None else [s for s in by_feed(feed, usable_only=True) if s.kind in ("rss", "sitemap")]):
        try:
            entries = fetch_sitemap(src, store, now) if src.kind == "sitemap" else fetch(src.url)
        except Exception as ex:  # one broken feed must not stop the run
            report.feed_errors.append((src.id, f"{type(ex).__name__}: {str(ex)[:80]}"))
            continue
        report.sources_ok += 1
        fresh = [e for e in entries if e.link and (e.date is None or e.date >= cutoff)]
        report.entries_in_window += len(fresh)
        if src.kind == "sitemap":
            new = fresh if refresh else [e for e in fresh if _page_changed(store, e)]
        else:
            new = fresh if refresh else [e for e in fresh if not store.seen(url_key(e.link))]  # refresh: re-triage what was seen
        report.already_seen += len(fresh) - len(new)
        new.sort(key=lambda e: e.date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        report.over_cap += max(0, len(new) - per_source_cap)  # not marked seen: picked up on a later run
        candidates += [(src, e) for e in new[:per_source_cap]]
    candidates.sort(key=lambda p: p[1].date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    report.over_cap += max(0, len(candidates) - max_docs)
    candidates = candidates[:max_docs]
    log(f"fetched {report.sources_ok} feeds ({len(report.feed_errors)} failed): {report.entries_in_window} entries in the last {days} days, "
        f"{report.already_seen} already seen, {len(candidates)} to process")

    for i, (src, entry) in enumerate(candidates, 1):
        key = url_key(entry.link)
        watched = src.kind == "sitemap"
        lastmod = entry.date.isoformat() if entry.date else None
        doc = entry_to_document(src, entry)
        if doc is None:
            report.skipped["paywalled"] += 1
            store.mark_seen(key, src.id, entry.link, entry.title, "skipped:paywalled")
            if watched:
                store.set_page_state(key, lastmod, None)
            continue
        if not doc.full_text:
            doc, why = ensure(doc)
            if doc is None:
                report.skipped[why] += 1
                if why not in TRANSIENT:
                    store.mark_seen(key, src.id, entry.link, entry.title, f"skipped:{why}")
                    if watched:
                        store.set_page_state(key, lastmod, None)  # final: not looked at again until the page is updated
                continue
        text_hash = hashlib.sha1(doc.body_text.encode()).hexdigest()
        if watched:
            old = store.page_state(key)
            if old and old["text_hash"] == text_hash:  # lastmod moved but the text did not: no model call
                store.set_page_state(key, lastmod, text_hash)
                report.skipped["unchanged"] += 1
                continue
            report.updated += 1 if old and old["text_hash"] else 0
        try:
            item = triage(doc)
        except LLMError as ex:
            report.llm_errors.append((src.id, str(ex)[:100]))
            continue
        if watched:
            store.set_page_state(key, lastmod, text_hash)
        if item is None:
            report.skipped["no_item"] += 1
            store.mark_seen(key, src.id, doc.url, doc.title, "skipped:no_item")
            continue
        fi = FeedItem(item, src, doc.published, unverified_numbers(doc.body_text, item.summary_2_lines))
        for other in report.items:  # simple near-duplicate title check; embedding-based dedupe is not built yet
            if difflib.SequenceMatcher(None, other.item.title.lower(), item.title.lower()).ratio() >= 0.9:
                fi.duplicate_of = other.item.doc_id
                break
        report.items.append(fi)
        store.save_item(url_key=key, feed=feed, section=src.section, published=doc.published.isoformat() if doc.published else None,
                        item=item, unverified=fi.unverified)
        store.mark_seen(key, src.id, doc.url, doc.title, "triaged")
        log(f"  [{i}/{len(candidates)}] r{item.relevance} {src.id:16} {item.title[:70]}")
    report.seconds = time.time() - t0
    report.usage = _usage_since(usage_offset)
    return report
