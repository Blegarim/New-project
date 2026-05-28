# CLAUDE.md — Research Assistant Agent

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
    ├──► agent/memory.py   (message history + context trimming)        │
    │                                                                   │
    ├──► models/claude_client.py  (Anthropic API, tool_use)            │
    │         │                                                         │
    │         ▼                                                         │
    │    [Claude decides which tool to call]                            │
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
│   └── claude_client.py ← thin wrapper around anthropic.Anthropic
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
| LLM brain      | Anthropic Claude API       | Yes (ANTHROPIC_API_KEY) | Use `claude-haiku-4-5` to keep costs low |
| Web search     | `duckduckgo-search` package | No           | pip package, no account needed            |
| Page reader    | Jina AI Reader             | No           | GET `https://r.jina.ai/<url>` → markdown  |
| Encyclopedia   | `wikipedia` package        | No           | pip package wrapping Wikipedia REST API   |
| Storage        | Local filesystem           | No           | Plain file I/O                            |

---

## 5. Config Layer — `config/settings.py`

Use `pydantic-settings` to load `.env` values.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 4096
    max_loop_iterations: int = 10    # safety cap on the ReAct loop
    reports_dir: str = "reports"
    jina_base_url: str = "https://r.jina.ai/"

    class Config:
        env_file = ".env"

settings = Settings()
```

`.env.example` must contain:
```
ANTHROPIC_API_KEY=your_key_here
```

---

## 6. Model Layer — `models/claude_client.py`

Thin wrapper. Responsible only for making the API call and returning the raw response.
Does NOT handle tool dispatch or loop logic.

```python
import anthropic
from config.settings import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

def call_claude(messages: list[dict], tools: list[dict], system: str) -> anthropic.types.Message:
    return client.messages.create(
        model=settings.model,
        max_tokens=settings.max_tokens,
        system=system,
        tools=tools,
        messages=messages,
    )
```

Key points:
- Always pass `tools` so Claude can call them.
- `system` is the full system prompt (built by `planner.py`).
- Return the raw `Message` object; let `core.py` inspect `stop_reason` and `content`.

---

## 7. Tools Layer

### 7.1 Tool Schema Definitions — `tools/registry.py`

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
from tools.search import search_web
from tools.fetch_page import fetch_page
from tools.wikipedia import lookup_wikipedia
from tools.file_ops import save_report

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

### 7.2 `tools/search.py`

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

### 7.3 `tools/fetch_page.py`

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

### 7.4 `tools/wikipedia.py`

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

### 7.5 `tools/file_ops.py`

```python
import os
from config.settings import settings

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

### 8.1 Memory — `agent/memory.py`

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

### 8.2 Planner — `agent/planner.py`

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

### 8.3 Core Loop — `agent/core.py`

This is the heart of the agent. Implements the **ReAct** pattern:
**Re**ason (Claude thinks) → **Act** (call a tool) → **Observe** (get result) → repeat.

```python
from agent.memory import Memory
from agent.planner import build_system_prompt
from models.claude_client import call_claude
from tools.registry import TOOL_SCHEMAS, dispatch
from config.settings import settings

def run_agent(question: str) -> dict:
    memory = Memory()
    system = build_system_prompt(question)
    memory.add_user(f"Please research the following question: {question}")

    for iteration in range(settings.max_loop_iterations):
        print(f"\n[Loop {iteration + 1}/{settings.max_loop_iterations}]")

        response = call_claude(
            messages=memory.get(),
            tools=TOOL_SCHEMAS,
            system=system
        )

        # Add the assistant's response to memory (raw content list)
        memory.add_assistant(response.content)

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
pydantic-settings>=2.0.0
duckduckgo-search>=6.0.0
requests>=2.31.0
wikipedia>=1.4.0
python-dotenv>=1.0.0
```

---

## 11. `.env.example`

```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
# Optional overrides:
# MODEL=claude-haiku-4-5-20251001
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

1. `config/settings.py` — verify env loading works
2. `tools/search.py` → test standalone: `python -c "from tools.search import search_web; print(search_web('Python agent'))"`
3. `tools/fetch_page.py` → test standalone
4. `tools/wikipedia.py` → test standalone
5. `tools/file_ops.py` → test standalone
6. `tools/registry.py` (schemas + dispatcher)
7. `models/claude_client.py` → test with a simple message (no tools yet)
8. `agent/memory.py`
9. `agent/planner.py`
10. `agent/core.py` — the full loop
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
