# Build Log (rolling)

Raw record of every command, output, error and fix, kept as input for the blog post (see the series: https://www.vineetganti.com/blog/series/agentic-ai).

Conventions
- Newest entry goes at the bottom. Each entry is dated and says who ran what.
- Only things that actually happened. No invented output.
- Secrets, tokens and personal paths are redacted (`<project-root>` = the repo folder).
- Failures and dead ends stay in.

---

## Entry 1 — 2026-11-02 — Project kickoff and Stage 1 scaffolding

**Goal:** turn the pasted implementation plan (Gmail → parse → dedupe → LLM summary → brief UI → approve → Notion) into a learning build, with Claude giving "middle ground" guidance rather than building everything.

**Environment (as reported by the session):** Windows 11, PowerShell primary shell, Python project, not a git repository, model Claude Sonnet 5.5 in the VS Code extension.

### 1.1 Inspect the pre-created scaffold (Claude)

Tools used: `Glob` (`**/*`) and `Read` on `pipeline.py`.

Findings:
- `Read` of `src/newsletter_brief/pipeline.py` returned a warning: file exists but is empty.
- `Glob` showed the full folder tree already existed: `src/newsletter_brief/{ingest,parse,dedupe,summarize,brief,notion,memory,db}/`, plus `tests/`, `evals/`, `scripts/`, `data/`, `docs/`, `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`.

Command (Bash, from project root):
```bash
wc -c $(find src tests scripts evals -name "*.py") | sort -n | tail -50
cat pyproject.toml .env.example README.md
head -c 1500 docs/plan.md
```
Output, summarized:
- `wc -c` reported 0 bytes for every `.py` file → the whole scaffold is empty stubs.
- `pyproject.toml`: Python >=3.11; deps google-api-python-client, google-auth-oauthlib, beautifulsoup4, trafilatura, httpx, pydantic>=2, chromadb, gradio, notion-client, python-dotenv; dev deps pytest, ruff; console script `nb = newsletter_brief.cli:main`.
- `.env.example`: keys for Google client secrets/token path, Gemini key, Notion token + 3 DB ids, DB path, `MAX_ITEMS_PER_DAY=30`.
- `README.md`: build order and layout matching the plan.
- `docs/plan.md`: only the placeholder `(Paste the implementation plan here.)`.

**Decision:** since every file is empty, split the work. Claude writes boilerplate with little learning value; the user writes the core Stage 1 logic. Rationale: user wants to learn how to build agents, so parsing/canonicalizing/Gmail fetch stay as the user's exercises, and Stage 2 (structured output, prompt-injection boundary, evals) is where agent concepts start.

### 1.2 Files written by Claude

| File | Content |
|---|---|
| `src/newsletter_brief/config.py` | `Settings` dataclass loaded from `.env` via python-dotenv (paths, `max_items_per_day`, `raw_dir`). |
| `src/newsletter_brief/schemas.py` | Pydantic models `RawEmail`, `Link`, `ParsedEmail` (Stage 1 only). |
| `src/newsletter_brief/ingest/auth.py` | Gmail OAuth, scope `gmail.readonly` only. Refreshes token; if refresh fails (test-mode tokens expire ~7 days) falls back to the browser flow. |
| `scripts/auth_gmail.py` | Calls `users().getProfile` and prints the authorized address, to verify auth. |
| `src/newsletter_brief/ingest/gmail_client.py` | Stub `fetch_emails()` raising `NotImplementedError`, docstring with hints (list returns ids only; `get(format="full")`; nested MIME parts; base64url; save raw JSON to `data/raw/`). |
| `src/newsletter_brief/parse/canonicalize.py` | Stubs `canonicalize()` and `is_content_link()` with hints. |
| `tests/test_parse.py` | Five tests acting as the spec for `canonicalize` / `is_content_link` (strip tracking params, normalize param order and trailing slash, equal URLs across different tracking, drop unsubscribe/view-in-browser/social/mailto, keep real article). |

Design notes:
- Read-only scope chosen deliberately so the agent can never send or delete mail.
- `canonicalize()` kept pure (no network); redirect resolving to be a separate function so the tests stay fast.

**Not run yet:** no install, no tests, no OAuth. The new tests are expected to fail (`NotImplementedError`) until the user implements `canonicalize.py`.

### 1.3 Plan document

`docs/plan.md` placeholder replaced with the full plan, reformatted into headings and bullets (content unchanged).

### 1.4 Blog tooling

- User supplied their blog-drafting prompt and the series URL (https://www.vineetganti.com/blog/series/agentic-ai). Both were saved to Claude's memory for later use.
- This file (`docs/build-log.md`) created as the rolling log. It is updated only when the user asks.

### Next steps (user)
1. Google Cloud setup: project, enable Gmail API, Desktop OAuth client → `credentials.json` in project root, add self as test user.
2. `pip install -e ".[dev]"`, then `python scripts/auth_gmail.py`.
3. Implement `canonicalize.py` until `pytest tests/test_parse.py` passes.
4. Implement `fetch_emails()`, then `html_to_text.py` / `links.py`, then `nb fetch` in `cli.py`.

### Open questions / gaps for the blog
- None of the commands above produced errors yet; the first real failure/debug material will come from OAuth setup and install.
- The series URL has not been fetched yet, so the style reference is not reflected in this log.
