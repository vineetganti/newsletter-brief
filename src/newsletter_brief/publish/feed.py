"""Public feed for vineetganti.com: JSON Feed 1.1 and RSS 2.0, built ONLY from items the user marked "Publish on my site".

This writes local files and uploads nothing. The public contract is a strict whitelist: the original article's title and link,
the source name, the date, a short summary grounded in the article text, the category and badges, and the model's "why it
matters" line explicitly labelled as AI-written. Never included: article body text, raw emails, the user's notes and decisions,
relevance scores, unverified-figure flags, tokens or any private field.
"""
import json
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from newsletter_brief.brief.build import DigestItem, buckets

SITE = "https://www.vineetganti.com"
TITLE = "Vineet Ganti: Engineering and AI reading list"
DESCRIPTION = ("Articles picked from company engineering and AI research blogs. Summaries are generated from the article text "
               "and checked automatically; follow each link for the original.")


def public_items(items: list[DigestItem]) -> list[DigestItem]:
    """Published, not skipped, once each, in the order of the digest's buckets."""
    groups, _ = buckets(items)
    return [i for _, rows in groups for i in rows if i.publish and i.decision != "skip"]


def _tags(i: DigestItem) -> list[str]:
    tags = [i.category] if i.category else []
    tags += [t for t, on in (("open-source", i.open_source), ("breakthrough", i.breakthrough), ("top-learning", i.top_learning)) if on]
    return tags + ([i.tag] if i.tag else [])


def to_json_feed(items: list[DigestItem], site: str = SITE) -> dict:
    return {
        "version": "https://jsonfeed.org/version/1.1", "title": TITLE, "home_page_url": f"{site}/reading",
        "feed_url": f"{site}/reading/feed.json", "description": DESCRIPTION, "language": "en",
        "items": [{
            "id": i.doc_id, "url": f"{site}/reading#{i.doc_id}", "external_url": i.url, "title": i.title,
            "content_text": i.summary,
            "date_published": (i.published or datetime.now(timezone.utc)).isoformat(),
            "tags": _tags(i), "authors": [{"name": i.source_name}],
            "_ai_note": {"label": "Written by an AI model, not the article's author", "why_it_matters": i.why},
        } for i in public_items(items)],
    }


def to_rss(items: list[DigestItem], site: str = SITE) -> str:
    rows = []
    for i in public_items(items):
        pub = format_datetime(i.published or datetime.now(timezone.utc))
        desc = f"{i.summary}\n\nAI-written note on why it matters: {i.why}\n\nSource: {i.source_name}"
        rows.append(f"    <item>\n      <title>{escape(i.title)}</title>\n      <link>{escape(i.url)}</link>\n"
                    f"      <guid isPermaLink=\"false\">{escape(i.doc_id)}</guid>\n      <pubDate>{pub}</pubDate>\n"
                    + "".join(f"      <category>{escape(t)}</category>\n" for t in _tags(i))
                    + f"      <description>{escape(desc)}</description>\n    </item>")
    return ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<rss version=\"2.0\">\n  <channel>\n"
            f"    <title>{escape(TITLE)}</title>\n    <link>{site}/reading</link>\n    <description>{escape(DESCRIPTION)}</description>\n"
            + "\n".join(rows) + "\n  </channel>\n</rss>\n")


def write_public_feed(items: list[DigestItem], out_dir: Path, site: str = SITE) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "feed.json").write_text(json.dumps(to_json_feed(items, site), indent=1, ensure_ascii=False), encoding="utf-8")
    (out_dir / "feed.xml").write_text(to_rss(items, site), encoding="utf-8")
    return len(public_items(items))
