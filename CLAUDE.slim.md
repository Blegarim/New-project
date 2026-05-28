# CLAUDE.md — Research Assistant Agent

Python agent that researches a question autonomously using Claude tool_use,
then saves a markdown report. Entry point: `main.py`. All source under `research_agent/`.

---

## Architecture

```
main.py → agent/core.py (ReAct loop)
              ├── agent/planner.py   (system prompt)
              ├── agent/memory.py    (canonical message history)
              ├── models/factory.py → models/provider.py  (LLMProvider Protocol)
              │       ├── adapters/anthropic_adapter.py   (Anthropic)
              │       └── adapters/openai_adapter.py      (OpenAI-compatible:
              │                                            Groq, Cerebras,
              │                                            OpenRouter, Ollama)
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
├── models/       provider.py  factory.py
│                 adapters/    anthropic_adapter.py  openai_adapter.py
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
- **Provider is pluggable** — `core.py` calls `get_provider()` from `models/factory.py` and only sees a `NormalizedResponse`. Switch backends with `PROVIDER=anthropic` or `PROVIDER=openai_compat` in `.env`. New backends = one adapter file.
- **Memory stores canonical (Anthropic-style) dicts** — adapters translate to/from provider-native format at call time, never inside the loop.
- **Default model is `claude-haiku-4-5-20251001`** — cheapest Claude; switch to Sonnet in `.env` if reasoning quality is lacking, or to a free provider via `PROVIDER=openai_compat`.
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
PROVIDER=anthropic                       # or "openai_compat"
MODEL=claude-haiku-4-5-20251001          # provider-specific model id

# Anthropic (PROVIDER=anthropic)
ANTHROPIC_API_KEY=...

# OpenAI-compatible (PROVIDER=openai_compat)
# OPENAI_API_KEY=...
# BASE_URL=https://api.groq.com/openai/v1       # Groq
# BASE_URL=https://api.cerebras.ai/v1            # Cerebras
# BASE_URL=http://localhost:11434/v1             # Ollama (no key needed)

MAX_LOOP_ITERATIONS=10           # optional override
```
