import argparse
import re
import sys

from newsletter_brief.ingest import allowlist
from newsletter_brief.ingest.gmail_client import fetch_newsletters, load_raw_emails
from newsletter_brief.parse.redirects import Resolver, resolve_offline
from newsletter_brief.pipeline import parse_email

LONG_URL = re.compile(r"\((https?://[^)\s]{80,})\)")


def _shorten(text: str) -> str:
    """Display only: tracking URLs can be thousands of characters long."""
    return LONG_URL.sub(lambda m: f"({m.group(1)[:70]}...[{len(m.group(1))} chars])", text)


def _fetch(args: argparse.Namespace) -> None:
    if args.offline:
        emails = load_raw_emails()
    else:
        emails = fetch_newsletters(f"newer_than:{args.days}d")
    resolver = resolve_offline if args.no_resolve else Resolver()
    entries = allowlist.list_senders()
    emails = [e for e in emails if allowlist.is_allowed(e.sender_addr, entries)]
    print(f"{len(emails)} newsletter(s)\n")
    for email in emails[: args.limit]:
        parsed = parse_email(email, resolver)
        print("=" * 80)
        print(f"{parsed.sender_addr} | {parsed.subject}")
        print(f"text: {len(parsed.body_text)} chars | links kept: {len(parsed.links)}")
        print(_shorten(parsed.body_text)[: args.chars])
        print("-- links")
        for link in parsed.links[:10]:
            print(f"  {link.text[:60]!r} -> {link.url[:90]}")


def _daily(args: argparse.Namespace) -> None:
    from datetime import date

    from newsletter_brief.brief.build import load_items, render_markdown, to_json
    from newsletter_brief.config import ROOT
    from newsletter_brief.daily import run_feed
    from newsletter_brief.db.store import Store

    store = Store()
    from newsletter_brief.memory.semantic import describe_learning, make_triage

    print(describe_learning(store))
    report = run_feed(args.feed, days=args.days, per_source_cap=args.cap, max_docs=args.max_docs, refresh=args.refresh, store=store,
                      triage=make_triage(store))
    items = load_items(store, args.feed, args.days)  # the digest is a view over everything stored in the window
    out = ROOT / "data" / "out"
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{args.feed}-{date.today().isoformat()}"
    (out / f"{stem}.md").write_text(render_markdown(items, report, args.days), encoding="utf-8")
    (out / f"{stem}.json").write_text(to_json(items, args.feed, args.days), encoding="utf-8")
    print(f"\n{len(items)} articles in the digest ({len(report.items)} newly triaged) in {report.seconds:.0f}s | skipped {dict(report.skipped) or 'none'} | "
          f"model errors {len(report.llm_errors)} | feed errors {report.feed_errors or 'none'} | usage {report.usage}")
    print(f"wrote data/out/{stem}.md and .json")


def _eval(args: argparse.Namespace) -> None:
    from newsletter_brief.db.store import Store
    from newsletter_brief.memory.decisions import evaluate, format_report

    print(format_report(evaluate(Store())))


def _brief(args: argparse.Namespace) -> None:
    from newsletter_brief.brief.app import build_app

    build_app(feed=args.feed, days=args.days, show_publish_and_tags=args.publish_controls).launch(server_name="127.0.0.1", server_port=args.port)  # local only, never deployed


def _publish(args: argparse.Namespace) -> None:
    from newsletter_brief.brief.build import load_items
    from newsletter_brief.config import ROOT
    from newsletter_brief.db.store import Store
    from newsletter_brief.publish.feed import write_public_feed

    out = ROOT / "data" / "out" / "public"
    n = write_public_feed(load_items(Store(), args.feed, args.days), out, args.site)
    print(f"{n} items marked 'Publish on my site' written to {out.relative_to(ROOT)} (feed.json, feed.xml). Nothing was uploaded.")


def _allow(args: argparse.Namespace) -> None:
    if args.action == "add":
        allowlist.add_sender(args.addr, args.note)
    elif args.action == "remove":
        allowlist.remove_sender(args.addr)
    print("\n".join(allowlist.list_senders()))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
    parser = argparse.ArgumentParser(prog="nb")
    sub = parser.add_subparsers(dest="cmd", required=True)

    fetch = sub.add_parser("fetch", help="fetch + parse allowlisted newsletters, print to terminal")
    fetch.add_argument("--days", type=int, default=1)
    fetch.add_argument("--offline", action="store_true", help="re-parse data/raw/ without calling Gmail")
    fetch.add_argument("--no-resolve", action="store_true", help="skip following tracking redirects (offline unwrapping only)")
    fetch.add_argument("--limit", type=int, default=5, help="max emails to print")
    fetch.add_argument("--chars", type=int, default=1500, help="max text chars per email")
    fetch.set_defaults(func=_fetch)

    daily = sub.add_parser("daily", help="daily run for one feed: fetch sources, triage what is new, write the digest")
    daily.add_argument("--feed", default="engineering")
    daily.add_argument("--days", type=int, default=3, help="only entries from the last N days")
    daily.add_argument("--cap", type=int, default=5, help="max new entries per source per run")
    daily.add_argument("--max-docs", type=int, default=60, help="max documents per run")
    daily.add_argument("--refresh", action="store_true", help="re-triage items already seen in the window (after a prompt change)")
    daily.set_defaults(func=_daily)

    ev = sub.add_parser("eval", help="how well the model's scores agree with your ratings, and the gates for going automatic")
    ev.set_defaults(func=_eval)

    brief = sub.add_parser("brief", help="open the private curator page (approve / skip / top learning / publish) on localhost")
    brief.add_argument("--feed", default="engineering")
    brief.add_argument("--days", type=int, default=3)
    brief.add_argument("--port", type=int, default=7860)
    brief.add_argument("--publish-controls", action="store_true", help="show the 'Publish on my site' and Tag boxes (hidden during the rating phase)")
    brief.set_defaults(func=_brief)

    publish = sub.add_parser("publish", help="write the public feed files (only items you marked 'Publish on my site'); uploads nothing")
    publish.add_argument("--feed", default="engineering")
    publish.add_argument("--days", type=int, default=30)
    publish.add_argument("--site", default="https://www.vineetganti.com")
    publish.set_defaults(func=_publish)

    allow = sub.add_parser("allow", help="list/add/remove allowlisted senders")
    allow.add_argument("action", choices=["list", "add", "remove"])
    allow.add_argument("addr", nargs="?", default="")
    allow.add_argument("--note", default="")
    allow.set_defaults(func=_allow)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
