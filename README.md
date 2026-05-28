# Research Assistant Agent

An AI agent that researches any topic autonomously — searches the web, reads pages,
cross-checks Wikipedia, and writes a structured markdown report. Built as a hands-on
experiment for understanding how AI agents work.

---

## What It Does

Give it a question. It figures out the rest.

```
$ python main.py "How does transformer attention work?"

Researching: How does transformer attention work?
────────────────────────────────────────────────────────────

[Loop 1] [Tool] search_web({'query': 'transformer attention mechanism explained'})
[Loop 2] [Tool] fetch_page({'url': 'https://arxiv.org/abs/1706.03762'})
[Loop 3] [Tool] lookup_wikipedia({'topic': 'Attention (machine learning)'})
[Loop 4] [Tool] search_web({'query': 'transformer attention practical intuition'})
[Loop 5] [Tool] fetch_page({'url': 'https://jalammar.github.io/illustrated-transformer/'})
[Loop 6] [Tool] save_report({'filename': 'transformer_attention', 'content': '...'})
         [Tool] final_answer({'summary': 'Transformer attention allows...', ...})

[Done] Transformer attention allows each token to attend to all others...
Completed in 6 iterations.
Report: reports/transformer_attention.md
```

---

## How It Works

The agent uses the **ReAct** pattern (Reason + Act):

```
Question
   │
   ▼
┌──────────────────────────────────┐
│  Think: What do I need to find?  │
└──────────┬───────────────────────┘
           │ tool call
           ▼
┌──────────────────────────────────┐
│  Act: Call a tool                │◄──┐
│  • search_web                    │   │
│  • fetch_page                    │   │ loop
│  • lookup_wikipedia              │   │ (up to 10x)
│  • save_report                   │   │
└──────────┬───────────────────────┘   │
           │ result                    │
           ▼                           │
┌──────────────────────────────────┐   │
│  Observe: What did I learn?      │───┘
└──────────────────────────────────┘
           │ enough info?
           ▼
     final_answer → report saved
```

The LLM (Claude) is the brain. It decides which tools to call and in what order.
All external calls are handled by the tools layer. The agent loop orchestrates
the message history that connects them.

---

## Architecture

```
research_agent/
├── agent/
│   ├── core.py          # ReAct loop — the main engine
│   ├── planner.py       # System prompt that instructs the agent
│   └── memory.py        # Manages message history for the API
├── tools/
│   ├── registry.py      # Tool schemas (what Claude sees) + dispatcher
│   ├── search.py        # DuckDuckGo web search (free, no key)
│   ├── fetch_page.py    # Jina AI URL reader (free, no key)
│   ├── wikipedia.py     # Wikipedia lookup (free, no key)
│   └── file_ops.py      # Save reports locally
├── models/
│   ├── provider.py      # LLMProvider Protocol + canonical types
│   ├── factory.py       # Picks an adapter from settings.provider
│   └── adapters/
│       ├── anthropic_adapter.py  # Anthropic native
│       └── openai_adapter.py     # OpenAI-compatible: Groq/Cerebras/Ollama/…
├── config/
│   └── settings.py      # Environment config (pydantic-settings)
├── main.py              # CLI entry point
reports/                 # Generated markdown reports (git-ignored)
```

### APIs Used

| Purpose      | Service                                 | Cost  |
|--------------|-----------------------------------------|-------|
| LLM brain    | Anthropic Claude API (default)          | Paid (key required) |
| LLM brain    | Groq / Cerebras (OpenAI-compatible)     | Free tier, key required |
| LLM brain    | Ollama (local, OpenAI-compatible)       | Free, no key, runs locally |
| Web search   | DuckDuckGo                              | Free, no key |
| Page reader  | Jina AI Reader                          | Free, no key |
| Encyclopedia | Wikipedia                               | Free, no key |

The LLM backend is pluggable: set `PROVIDER=anthropic` (default) or
`PROVIDER=openai_compat` (with a `BASE_URL`) in `.env`. With Groq's free tier
or local Ollama the whole agent runs at zero marginal cost. With Anthropic,
a full research run on `claude-haiku-4-5` costs roughly **$0.001–$0.005**.

---

## Setup

**Requirements:** Python 3.10+, and one of:
- An [Anthropic API key](https://console.anthropic.com/) (default), or
- A free key from [Groq](https://console.groq.com/) / [Cerebras](https://cloud.cerebras.ai/), or
- A local [Ollama](https://ollama.com/) install (no key, runs offline)

```bash
# 1. Clone and enter the project
git clone https://github.com/Blegarim/New-project
cd New-project

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your provider
cp .env.example .env
# Edit .env:
#   - default:  ANTHROPIC_API_KEY=...
#   - free:     PROVIDER=openai_compat   BASE_URL=https://api.groq.com/openai/v1
#               OPENAI_API_KEY=<groq key>   MODEL=llama-3.3-70b-versatile
#   - local:    PROVIDER=openai_compat   BASE_URL=http://localhost:11434/v1
#               MODEL=qwen2.5:7b
```

---

## Usage

```bash
# Pass the question as an argument
python main.py "What is retrieval-augmented generation and why is it useful?"

# Or run interactively
python main.py
Research question: What caused the 2008 financial crisis?
```

Reports are saved to `reports/<topic>.md`.

---

## Key Concepts This Project Demonstrates

| Concept | Where it lives | What to look at |
|---|---|---|
| **Tool calling** | `tools/registry.py` | JSON schema definitions; how the API receives and returns them |
| **ReAct loop** | `agent/core.py` | The `for` loop with `stop_reason` checks |
| **Message history** | `agent/memory.py` | How `tool_use` and `tool_result` pairs are structured |
| **System prompt** | `agent/planner.py` | How instructions shape agent behavior |
| **Tool dispatch** | `tools/registry.py` | Mapping tool names → Python functions |
| **Safety limits** | `config/settings.py` | `MAX_LOOP_ITERATIONS` cap |

---

## Extending the Agent

Some ideas once you understand the base:

- Add a `summarize_findings` intermediate tool to compress context mid-loop.
- Add a `send_email` tool (SMTP) to deliver reports.
- Add a Gemini adapter (`models/adapters/gemini_adapter.py`) — Gemini's tool
  schema dialect differs from Anthropic/OpenAI, so it needs its own translator.
- Add streaming output so you see the agent's thinking in real time.
- Add a vector store (ChromaDB, free) so the agent can remember past research sessions.

---

## Project Status

This is a learning experiment, not production software. See `CLAUDE.md` for the
full technical specification.

### Build Progress (per CLAUDE.md §13 implementation order)

| # | Component                              | Status        | Notes |
|---|----------------------------------------|---------------|-------|
| 1 | `config/settings.py`                   | Done          | env loading via pydantic-settings; provider-aware |
| 2 | `tools/search.py`                      | Done          | standalone test not yet logged |
| 3 | `tools/fetch_page.py`                  | Done          | standalone test not yet logged |
| 4 | `tools/wikipedia.py`                   | Done          | standalone test not yet logged |
| 5 | `tools/file_ops.py`                    | Done          | standalone test not yet logged |
| 6 | `tools/registry.py` (schemas+dispatch) | Done          | — |
| 7 | `models/` (provider + factory + adapters) | Done       | Anthropic adapter + OpenAI-compatible adapter; live API call not yet logged |
| 8 | `agent/memory.py`                      | Done          | stores canonical dict format |
| 9 | `agent/planner.py`                     | Done          | — |
| 10 | `agent/core.py` (ReAct loop)          | Done          | uses `get_provider()` |
| 11 | `main.py`                             | Done          | CLI + interactive mode |

### Open TODOs

- Run an end-to-end check with a real key (`ANTHROPIC_API_KEY` for default, or
  Groq/Cerebras key with `PROVIDER=openai_compat`) and confirm
  `python main.py "<question>"` produces a file in `reports/`.
- Log standalone sanity checks for each of the four tools.
- Once a successful end-to-end run is logged, swap `CLAUDE.md` for
  `CLAUDE.slim.md` per the spec header.
- Optional: add a Gemini adapter for Google AI Studio's free tier.
