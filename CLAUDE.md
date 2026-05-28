# CLAUDE.md — Research Assistant Agent

> **PRE-BUILD SPEC** — This file is intentionally verbose because the source files
> don't exist yet. It contains full code snippets to guide initial implementation.
>
> **Switch condition:** Once every file listed in Section 3 exists, `python main.py`
> runs end-to-end without errors, and at least one report has been generated in
> `reports/` — replace this file with `CLAUDE.slim.md`:
> ```bash
> mv CLAUDE.slim.md CLAUDE.md
> ```
> After the switch, delete `CLAUDE.slim.md` (it will have become `CLAUDE.md`).
> The slim version is ~70 lines and covers only what Claude Code needs during
> ongoing development, not what it needed to build from scratch.

This file is the authoritative technical reference for building this project.
Read it fully before writing any code. Follow the specs exactly.

---

## 1. Project Goal

Build a **Research Assistant Agent** in Python that:
1. Accepts a natural-language research question from the user (CLI input).
2. Autonomously plans and executes a multi-step research loop.
3. Uses four external tools (web search, page fetching, Wikipedia lookup, file I/O).
4. Stops when it has enough information to write a structured report.
5. Saves the final report as a markdown file in `reports/`.

This is a **learning project** — the goal is to understand the agent loop, tool calling,
and memory management. Prefer clarity over cleverness in all code.

---

## 2. Architecture Overview

```
User (CLI)
    │
    ▼
main.py  ──────────────────────────────────────────────────────────────┐
    │                                                                   │
    ▼                                                                   │
agent/core.py  (ReAct loop)                                            │
    │                                                                   │
    ├──► agent/planner.py  (system prompt + initial plan)              │
    │                                                                   │
    ├──► agent/memory.py   (canonical message history)                 │
    │                                                                   │
    ├──► models/factory.py  → models/provider.py (LLMProvider)         │
    │         │                                                         │
    │         ├── adapters/anthropic_adapter.py  (Anthropic native)    │
    │         └── adapters/openai_adapter.py     (OpenAI-compatible:   │
    │                                              Groq, Cerebras,     │
    │                                              OpenRouter, Ollama, │
    │                                              OpenAI)             │
    │         │                                                         │
    │         ▼                                                         │
    │    [LLM decides which tool to call → NormalizedResponse]          │
    │         │                                                         │
    └──► tools/registry.py  (dispatches to the right tool)             │
              │                                                         │
              ├── tools/search.py       (DuckDuckGo — no key needed)   │
              ├── tools/fetch_page.py   (Jina Reader — no key needed)  │
              ├── tools/wikipedia.py    (Wikipedia API — no key)       │
              └── tools/file_ops.py     (local read/write)             │
                                                                        │
    Final answer ──────────────────────────────────────────────────────┘
         │
         ▼
    reports/<slug>.md
```

The loop runs until Claude returns a `final_answer` tool call (not a text response),
signalling that research is complete and the report has been saved.

---

## 3. Directory Structure

```
research_agent/          ← all source code lives here
├── agent/
│   ├── __init__.py
│   ├── core.py          ← main ReAct loop
│   ├── planner.py       ← system prompt builder
│   └── memory.py        ← message history manager
├── tools/
│   ├── __init__.py
│   ├── registry.py      ← tool schema definitions + dispatcher
│   ├── search.py        ← DuckDuckGo web search
│   ├── fetch_page.py    ← Jina AI URL-to-markdown reader
│   ├── wikipedia.py     ← Wikipedia summary lookup
│   └── file_ops.py      ← save_report / read_file
├── models/
│   ├── __init__.py
│   ├── provider.py      ← LLMProvider Protocol + ContentBlock + NormalizedResponse
│   ├── factory.py       ← picks an adapter from settings.provider
│   └── adapters/
│       ├── __init__.py
│       ├── anthropic_adapter.py  ← Anthropic native
│       └── openai_adapter.py     ← OpenAI-compatible (Groq, Cerebras, …)
├── config/
│   └── settings.py      ← pydantic-settings config from .env
reports/                 ← generated markdown reports land here (git-ignored)
main.py                  ← CLI entry point
requirements.txt
.env.example
.gitignore
```

---

## 4. Free APIs Used

| Tool           | API / Library              | Key Required | Notes                                      |
|----------------|----------------------------|--------------|--------------------------------------------|
| LLM brain      | Anthropic Claude API       | Yes (ANTHROPIC_API_KEY) | Default; `claude-haiku-4-5` keeps costs low |
| LLM brain (free) | Groq, Cerebras (OpenAI-compatible) | Free key   | Set `PROVIDER=openai_compat` + `BASE_URL`   |
| LLM brain (local) | Ollama (OpenAI-compatible) | None        | `BASE_URL=http://localhost:11434/v1`        |
| Web search     | `duckduckgo-search` package | No           | pip package, no account needed            |
| Page reader    | Jina AI Reader             | No           | GET `https://r.jina.ai/<url>` → markdown  |
| Encyclopedia   | `wikipedia` package        | No           | pip package wrapping Wikipedia REST API   |
| Storage        | Local filesystem           | No           | Plain file I/O                            |

---

## 5. Config Layer — `research_agent/config/settings.py`

Use `pydantic-settings` to load `.env` values. The `provider` field selects
the LLM backend; credentials for all supported providers live side-by-side
so swapping is a one-line `.env` change.

```python
from typing import Literal
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    provider: Literal["anthropic", "openai_compat"] = "anthropic"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    base_url: str | None = None    # OpenAI-compatible: Groq, Cerebras, Ollama, …

    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 4096
    max_loop_iterations: int = 10
    reports_dir: str = "reports"
    jina_base_url: str = "https://r.jina.ai/"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
```

`.env.example` shows both provider configurations; see Section 11.

---

## 6. Provider Layer — `research_agent/models/`

The provider layer is the plug-and-play LLM abstraction. `core.py` only ever
sees a canonical (Anthropic-style) message format and a `NormalizedResponse`.
Each adapter owns translation in and out of its provider-native format.

### 6.1 Canonical Interface — `models/provider.py`

```python
from dataclasses import dataclass
from typing import Any, Literal, Protocol

@dataclass
class ContentBlock:
    type: Literal["text", "tool_use"]
    text: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict | None = None

    def to_dict(self) -> dict:
        if self.type == "text":
            return {"type": "text", "text": self.text}
        if self.type == "tool_use":
            return {"type": "tool_use", "id": self.id, "name": self.name,
                    "input": self.input or {}}

@dataclass
class NormalizedResponse:
    stop_reason: Literal["tool_use", "end_turn", "max_tokens", "stop"]
    content: list[ContentBlock]
    raw: Any = None

class LLMProvider(Protocol):
    def call(self, messages: list[dict], tools: list[dict], system: str
             ) -> NormalizedResponse: ...
```

### 6.2 Factory — `models/factory.py`

```python
from research_agent.config.settings import settings
from research_agent.models.provider import LLMProvider

def get_provider() -> LLMProvider:
    name = settings.provider
    if name == "anthropic":
        from research_agent.models.adapters.anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter()
    if name == "openai_compat":
        from research_agent.models.adapters.openai_adapter import OpenAICompatAdapter
        return OpenAICompatAdapter()
    raise ValueError(f"Unknown provider: {name!r}")
```

Adapters import lazily so a missing optional dep (e.g. `openai` not installed)
never breaks the alternate path.

### 6.3 Anthropic Adapter — `models/adapters/anthropic_adapter.py`

Passthrough. Canonical format matches Anthropic's wire format, so messages and
tools go through untouched; only the response object is normalized into
`ContentBlock`s.

### 6.4 OpenAI-compatible Adapter — `models/adapters/openai_adapter.py`

Translates in both directions:

- **Outbound messages**: assistant `tool_use` blocks → `assistant.tool_calls`;
  user `tool_result` blocks → `role: "tool"` messages with `tool_call_id`.
- **Outbound tools**: `{name, description, input_schema}` →
  `{type: "function", function: {name, description, parameters}}`.
- **Inbound response**: `message.content` → text block; `message.tool_calls` →
  `tool_use` blocks (arguments JSON-parsed). `finish_reason == "tool_calls"`
  maps to `stop_reason = "tool_use"`.

One adapter covers OpenAI, Groq, Cerebras, OpenRouter, Together, Fireworks,
and Ollama — anything that speaks the OpenAI Chat Completions API.

---

## 7. Tools Layer

### 7.1 Tool Schema Definitions — `research_agent/tools/registry.py`

All tool schemas follow the Anthropic `tool_use` format exactly.
Define them as a list of dicts. The dispatcher maps tool names to functions.

```python
TOOL_SCHEMAS = [
    {
        "name": "search_web",
        "description": "Search the web using DuckDuckGo. Returns a list of result titles, URLs, and snippets. Use this to find relevant sources for a research topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query string."},
                "num_results": {"type": "integer", "description": "Number of results to return (1–10).", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_page",
        "description": "Fetch the full text content of a URL as clean markdown. Use this after search_web to read a promising source in detail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The full URL to fetch."}
            },
            "required": ["url"]
        }
    },
    {
        "name": "lookup_wikipedia",
        "description": "Look up a topic on Wikipedia and return a summary (first ~500 words). Good for factual grounding and definitions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The Wikipedia article title or search term."}
            },
            "required": ["topic"]
        }
    },
    {
        "name": "save_report",
        "description": "Save the final research report as a markdown file. Call this ONLY when you have finished all research and are ready to write the complete report.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename without extension (e.g. 'quantum_computing_overview')."},
                "content": {"type": "string", "description": "Full markdown content of the report."}
            },
            "required": ["filename", "content"]
        }
    },
    {
        "name": "final_answer",
        "description": "Signal that the research is complete. Call this after save_report with a short summary of what was found and where the report was saved.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "1–3 sentence summary of findings."},
                "report_path": {"type": "string", "description": "Path to the saved report file."}
            },
            "required": ["summary", "report_path"]
        }
    }
]
```

The dispatcher in `registry.py`:

```python
from research_agent.tools.search import search_web
from research_agent.tools.fetch_page import fetch_page
from research_agent.tools.wikipedia import lookup_wikipedia
from research_agent.tools.file_ops import save_report

TOOL_FUNCTIONS = {
    "search_web": search_web,
    "fetch_page": fetch_page,
    "lookup_wikipedia": lookup_wikipedia,
    "save_report": save_report,
    "final_answer": None,   # handled directly in core.py, not dispatched
}

def dispatch(tool_name: str, tool_input: dict) -> str:
    fn = TOOL_FUNCTIONS.get(tool_name)
    if fn is None:
        raise ValueError(f"Unknown or non-dispatchable tool: {tool_name}")
    return fn(**tool_input)
```

### 7.2 `research_agent/tools/search.py`

```python
from duckduckgo_search import DDGS
import json

def search_web(query: str, num_results: int = 5) -> str:
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=num_results):
            results.append({
                "title": r.get("title"),
                "url": r.get("href"),
                "snippet": r.get("body")
            })
    return json.dumps(results, indent=2)
```

### 7.3 `research_agent/tools/fetch_page.py`

Jina Reader turns any URL into clean markdown via a simple GET request.
No API key needed for basic usage (rate-limited but sufficient for experiments).

```python
import requests

JINA_BASE = "https://r.jina.ai/"

def fetch_page(url: str) -> str:
    response = requests.get(
        JINA_BASE + url,
        headers={"Accept": "text/markdown"},
        timeout=20
    )
    response.raise_for_status()
    # Truncate to avoid flooding the context window
    text = response.text
    return text[:8000] + "\n\n[TRUNCATED]" if len(text) > 8000 else text
```

### 7.4 `research_agent/tools/wikipedia.py`

```python
import wikipedia

def lookup_wikipedia(topic: str) -> str:
    try:
        page = wikipedia.page(topic, auto_suggest=True)
        summary = wikipedia.summary(topic, sentences=10, auto_suggest=True)
        return f"**{page.title}**\nURL: {page.url}\n\n{summary}"
    except wikipedia.DisambiguationError as e:
        return f"Disambiguation — try one of: {e.options[:5]}"
    except wikipedia.PageError:
        return f"No Wikipedia page found for '{topic}'."
```

### 7.5 `research_agent/tools/file_ops.py`

```python
import os
from research_agent.config.settings import settings

def save_report(filename: str, content: str) -> str:
    os.makedirs(settings.reports_dir, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in filename)
    path = os.path.join(settings.reports_dir, safe_name + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Report saved to: {path}"
```

---

## 8. Agent Layer

### 8.1 Memory — `research_agent/agent/memory.py`

Manages the message history list passed to the Anthropic API.
Handles both regular messages and tool result messages.

```python
class Memory:
    def __init__(self):
        self.messages: list[dict] = []

    def add_user(self, text: str):
        self.messages.append({"role": "user", "content": text})

    def add_assistant(self, content: list):
        # content is the raw list from Message.content (may include tool_use blocks)
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_result(self, tool_use_id: str, result: str):
        # Tool results must be in a user message with type "tool_result"
        self.messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": result
            }]
        })

    def get(self) -> list[dict]:
        return self.messages
```

**Important**: Anthropic requires that after an `assistant` message containing
`tool_use` blocks, the next `user` message must contain `tool_result` blocks
with matching `tool_use_id`s. The loop in `core.py` enforces this.

### 8.2 Planner — `research_agent/agent/planner.py`

Builds the system prompt. The system prompt is the agent's "personality" and instructions.

```python
SYSTEM_PROMPT = """You are a rigorous research assistant. Your job is to answer research questions by:
1. Breaking the question into sub-topics.
2. Searching the web for relevant sources.
3. Reading key pages in full to extract facts.
4. Cross-checking important claims against Wikipedia.
5. Writing a structured, well-cited markdown report.

Rules you MUST follow:
- Always call at least one `search_web` and one `fetch_page` before writing the report.
- Do NOT fabricate facts. If you cannot find information, say so in the report.
- When you have gathered enough information (typically 3–5 sources), call `save_report` then `final_answer`.
- The report must have: Title, Summary, Key Findings (with sources), and Conclusion.
- Keep each tool call focused. Do not re-search the same query twice.
"""

def build_system_prompt(question: str) -> str:
    return SYSTEM_PROMPT + f"\n\nResearch question: {question}"
```

### 8.3 Core Loop — `research_agent/agent/core.py`

This is the heart of the agent. Implements the **ReAct** pattern:
**Re**ason (Claude thinks) → **Act** (call a tool) → **Observe** (get result) → repeat.

```python
from research_agent.agent.memory import Memory
from research_agent.agent.planner import build_system_prompt
from research_agent.config.settings import settings
from research_agent.models.factory import get_provider
from research_agent.tools.registry import TOOL_SCHEMAS, dispatch

def run_agent(question: str) -> dict:
    memory = Memory()
    system = build_system_prompt(question)
    provider = get_provider()
    memory.add_user(f"Please research the following question: {question}")

    for iteration in range(settings.max_loop_iterations):
        print(f"\n[Loop {iteration + 1}/{settings.max_loop_iterations}]")

        response = provider.call(
            messages=memory.get(),
            tools=TOOL_SCHEMAS,
            system=system,
        )

        # Serialize canonical ContentBlocks → dicts for memory.
        memory.add_assistant([b.to_dict() for b in response.content])

        # Check stop reason
        if response.stop_reason == "end_turn":
            # Claude gave a text response instead of using a tool — shouldn't happen
            # with our system prompt but handle gracefully
            text = next((b.text for b in response.content if b.type == "text"), "")
            print(f"[Agent] Unexpected end_turn: {text[:200]}")
            break

        if response.stop_reason == "tool_use":
            # Extract all tool_use blocks from this response
            tool_calls = [b for b in response.content if b.type == "tool_use"]

            for tool_call in tool_calls:
                tool_name = tool_call.name
                tool_input = tool_call.input
                tool_id = tool_call.id

                print(f"[Tool] {tool_name}({tool_input})")

                # Detect terminal tool
                if tool_name == "final_answer":
                    print(f"\n[Done] {tool_input['summary']}")
                    print(f"[Report] {tool_input['report_path']}")
                    # Still need to add a tool_result to close the message pair
                    memory.add_tool_result(tool_id, "Research complete.")
                    return {
                        "summary": tool_input["summary"],
                        "report_path": tool_input["report_path"],
                        "iterations": iteration + 1
                    }

                # Dispatch to the appropriate tool function
                try:
                    result = dispatch(tool_name, tool_input)
                except Exception as e:
                    result = f"Error running {tool_name}: {e}"

                print(f"[Result] {str(result)[:150]}...")
                memory.add_tool_result(tool_id, result)

    return {"error": "Max iterations reached without a final answer."}
```

**Loop invariant**: after every `assistant` message with `tool_use` blocks,
there must be a matching `user` message with all `tool_result` blocks. The loop
collects all tool calls from a single response before asking Claude again.

---

## 9. Entry Point — `main.py`

```python
import sys
from research_agent.agent.core import run_agent

def main():
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Research question: ").strip()

    if not question:
        print("Please provide a research question.")
        sys.exit(1)

    print(f"\nResearching: {question}\n{'─' * 60}")
    result = run_agent(question)

    if "error" in result:
        print(f"\nFailed: {result['error']}")
        sys.exit(1)
    else:
        print(f"\nCompleted in {result['iterations']} iterations.")
        print(f"Report: {result['report_path']}")

if __name__ == "__main__":
    main()
```

---

## 10. Dependencies — `requirements.txt`

```
anthropic>=0.40.0
openai>=1.0.0
pydantic-settings>=2.0.0
duckduckgo-search>=6.0.0
requests>=2.31.0
wikipedia>=1.4.0
python-dotenv>=1.0.0
```

---

## 11. `.env.example`

```
# Provider selection: "anthropic" or "openai_compat"
PROVIDER=anthropic
MODEL=claude-haiku-4-5-20251001

# --- Anthropic (PROVIDER=anthropic) ---
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# --- OpenAI-compatible (PROVIDER=openai_compat) ---
# Works with OpenAI, Groq, Cerebras, OpenRouter, Together, Fireworks, Ollama.
# Free options:
#   Groq:     BASE_URL=https://api.groq.com/openai/v1      MODEL=llama-3.3-70b-versatile
#   Cerebras: BASE_URL=https://api.cerebras.ai/v1          MODEL=llama-3.3-70b
#   Ollama:   BASE_URL=http://localhost:11434/v1           MODEL=qwen2.5:7b
# Paid:
#   OpenAI:   BASE_URL=                                    MODEL=gpt-4o-mini
# OPENAI_API_KEY=
# BASE_URL=

# Optional overrides:
# MAX_LOOP_ITERATIONS=10
```

---

## 12. `.gitignore` additions

```
.env
reports/
__pycache__/
*.pyc
.venv/
```

---

## 13. Implementation Order

Build in this order to allow incremental testing at each step:

1. `research_agent/config/settings.py` — verify env loading works
2. `research_agent/tools/search.py` → test standalone: `python -c "from research_agent.tools.search import search_web; print(search_web('Python agent'))"`
3. `research_agent/tools/fetch_page.py` → test standalone
4. `research_agent/tools/wikipedia.py` → test standalone
5. `research_agent/tools/file_ops.py` → test standalone
6. `research_agent/tools/registry.py` (schemas + dispatcher)
7. `research_agent/models/provider.py` → `models/adapters/anthropic_adapter.py` →
   `models/adapters/openai_adapter.py` → `models/factory.py` (test each adapter
   in isolation with a simple message before wiring into the loop)
8. `research_agent/agent/memory.py`
9. `research_agent/agent/planner.py`
10. `research_agent/agent/core.py` — the full loop, using `get_provider()`
11. `main.py`

---

## 14. Key Design Decisions

**Why `final_answer` as a tool?**
It gives Claude a structured way to signal completion with typed fields.
A text `end_turn` response is harder to parse reliably.

**Why Jina Reader instead of raw `requests` + BeautifulSoup?**
Jina converts any URL to clean markdown server-side. No parsing code needed,
and it handles JS-rendered pages. The free tier is sufficient for experiments.

**Why `claude-haiku-4-5` as default?**
Haiku is the fastest and cheapest Claude model. For a research loop that may
make 5–10 API calls, cost matters. Switch to Sonnet in settings if deeper
reasoning is needed.

**Why a provider Protocol + adapter pattern?**
The agent loop should not know which LLM it's talking to. Defining a
`LLMProvider` Protocol with a `NormalizedResponse` keeps `core.py` provider-
agnostic; adding a new backend means one adapter file, not edits across the
codebase. Memory stores messages in the canonical (Anthropic-style) dict
format; each adapter translates only at call time. The OpenAI-compatible
adapter covers OpenAI, Groq, Cerebras, OpenRouter, Together, Fireworks, and
Ollama with a single implementation — they all speak the same wire format.

**Why truncate `fetch_page` to 8000 chars?**
Claude's context window is large but each fetched page added to message history
accumulates. 8000 chars captures the key content of most articles while keeping
the total context manageable.

**Why `max_loop_iterations = 10`?**
Safety cap. A well-prompted agent finishes in 4–7 iterations. 10 prevents
runaway loops from burning API credits.

---

## 15. Example Agent Loop (Trace)

For the question: _"What is retrieval-augmented generation and why is it useful?"_

```
[Loop 1] → Claude thinks → calls search_web("retrieval augmented generation RAG")
           → gets 5 search results with URLs

[Loop 2] → Claude reads results → calls fetch_page("https://arxiv.org/...")
           → gets the full paper abstract + intro as markdown

[Loop 3] → Claude calls lookup_wikipedia("Retrieval-augmented generation")
           → gets Wikipedia summary

[Loop 4] → Claude calls search_web("RAG use cases production LLM")
           → gets more practical results

[Loop 5] → Claude calls fetch_page("https://blog.langchain.dev/...")
           → reads a practical explainer

[Loop 6] → Claude calls save_report("rag_overview", "# Retrieval-Augmented Generation\n...")
           → file saved to reports/rag_overview.md
           → Claude calls final_answer(summary="RAG combines...", report_path="reports/rag_overview.md")

[Done]
```

---

## 16. Running the Agent

```bash
# One-time setup
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your ANTHROPIC_API_KEY

# Run
python main.py "What is quantum computing and how does it work?"

# Or interactive mode
python main.py
```
