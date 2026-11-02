# Newsletter Brief

Gmail (read-only) -> parse -> dedupe -> LLM summaries -> daily brief UI -> approve -> Notion.

## Build order
1. Gmail fetch + parse, printed to terminal (no LLM) — `ingest/`, `parse/`
2. Structured extraction + dedupe + eval set — `summarize/`, `dedupe/`, `evals/`
3. Brief UI + schedule — `brief/`
4. Notion writer with approval + idempotency — `notion/`
5. Memory + ranking — `memory/`, `summarize/ranking.py`
6. Optional: "go deeper" second agent

## Layout
- `src/newsletter_brief/` — package, one subfolder per pipeline stage
- `evals/` — ~30 hand-labeled emails, metrics (link precision, faithfulness, dedupe accuracy)
- `scripts/` — one-off entry points (Gmail auth, daily run)
- `data/` — local raw emails, cache, SQLite (gitignored)
- `docs/` — plan and notes
