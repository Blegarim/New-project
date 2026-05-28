# CLAUDE.md — Research Assistant Agent

Python agent that researches a question autonomously using Claude tool_use,
then saves a markdown report. Entry point: `main.py`. All source under `research_agent/`.

---

## Architecture

```
main.py → agent/core.py (ReAct loop)
              ├── agent/planner.py   (system prompt)
              ├── agent/memory.py    (message history)
              ├── models/claude_client.py  (Anthropic API)
              └── tools/registry.py  (dispatch)
                    ├── search.py    → DuckDuckGo
                    ├── fetch_page.py → Jina Reader (r.jina.ai)
                    ├── wikipedia.py → wikipedia package
                    └── file_ops.py  → reports/
```

## Structure

```
research_agent/
├── agent/        core.py  planner.py  memory.py
├── tools/        registry.py  search.py  fetch_page.py  wikipedia.py  file_ops.py
├── models/       claude_client.py
├── config/       settings.py
main.py  requirements.txt  .env  reports/
```

## Run Commands

```bash
source .venv/bin/activate
python main.py "your question here"   # pass question as arg
python main.py                        # interactive mode
```

## Key Decisions

- **`final_answer` is a tool, not a text response** — structured termination; easier to parse than free-form `end_turn`.
- **Default model is `claude-haiku-4-5-20251001`** — cheapest Claude; switch to Sonnet in `.env` if reasoning quality is lacking.
- **Jina Reader (`r.jina.ai/<url>`)** strips pages to clean markdown server-side; no BeautifulSoup needed.
- **`fetch_page` truncates to 8000 chars** — prevents single pages from flooding the context window.
- **`MAX_LOOP_ITERATIONS=10`** — hard cap in `config/settings.py`; prevents runaway loops burning credits.
- **All tool results go back as `user` messages with `tool_result` blocks** — Anthropic requires this pairing after every `assistant` message that contains `tool_use` blocks. See `memory.py`.

## Gotchas

- After an assistant message with `tool_use`, the next user message **must** contain matching `tool_result` blocks (same `tool_use_id`). Missing this causes a 400 error.
- `duckduckgo-search` occasionally rate-limits. If search fails, the agent retries with a rephrased query — don't add sleep loops.
- Wikipedia `DisambiguationError` is handled in `tools/wikipedia.py`; it returns option suggestions rather than raising.
- `reports/` is git-ignored. Don't commit generated reports.

## Environment

```
ANTHROPIC_API_KEY=...          # required
MODEL=claude-haiku-4-5-20251001  # optional override
MAX_LOOP_ITERATIONS=10           # optional override
```
