# Research Assistant Agent — Implementation Plan

> Each session section is self-contained. Paste it fresh alongside CLAUDE.md at the start of each session.

---

## SESSION 1 — Scaffold & Config

**Goal:** Create the full directory skeleton, `.gitignore`, `.env.example`, `requirements.txt`, and the config layer. Nothing should import the Anthropic key yet — just verify `pydantic-settings` loads env vars correctly.

**What to build:**

1. Create the directory tree exactly as in CLAUDE.md §3:
   ```
   research_agent/
   ├── agent/__init__.py
   ├── tools/__init__.py
   ├── models/__init__.py
   config/
   └── settings.py
   reports/          (empty, git-ignored)
   main.py           (empty stub — just `pass`)
   requirements.txt
   .env.example
   .gitignore
   ```
   All `__init__.py` files are empty.

2. Write `requirements.txt` verbatim from CLAUDE.md §10.

3. Write `.env.example` verbatim from CLAUDE.md §11.

4. Write `.gitignore` additions from CLAUDE.md §12. Keep any existing content.

5. Write `config/settings.py` verbatim from CLAUDE.md §5.

6. Create a `.env` file (not committed) with a real `ANTHROPIC_API_KEY` value — copy from `.env.example` and fill in the key.

**Acceptance test (run this to verify):**
```bash
cd /home/user/New-project
python -c "
import sys; sys.path.insert(0, '.')
from research_agent.config.settings import settings
print('model:', settings.model)
print('max_iterations:', settings.max_loop_iterations)
print('Config OK')
"
```
Expected: prints model name and `Config OK` with no errors.

**Commit message:** `feat: scaffold project structure and config layer`

---

## SESSION 2 — Tools: search, fetch_page, wikipedia

**Goal:** Implement the three read-only research tools and verify each independently. No Anthropic calls yet.

**What to build:**

1. `research_agent/tools/search.py` — verbatim from CLAUDE.md §7.2.

2. `research_agent/tools/fetch_page.py` — verbatim from CLAUDE.md §7.3.

3. `research_agent/tools/wikipedia.py` — verbatim from CLAUDE.md §7.4.

**Note on imports:** These files live under `research_agent/tools/`, so any internal imports use `from research_agent.config.settings import settings` (not `from config.settings`).

**Acceptance tests (run each independently):**
```bash
# search
python -c "
import sys; sys.path.insert(0, '.')
from research_agent.tools.search import search_web
print(search_web('Python agent tutorial', num_results=2))
"

# fetch_page
python -c "
import sys; sys.path.insert(0, '.')
from research_agent.tools.fetch_page import fetch_page
print(fetch_page('https://en.wikipedia.org/wiki/Python_(programming_language)')[:300])
"

# wikipedia
python -c "
import sys; sys.path.insert(0, '.')
from research_agent.tools.wikipedia import lookup_wikipedia
print(lookup_wikipedia('Python programming language')[:300])
"
```
Each should return real content without errors.

**Commit message:** `feat: implement search, fetch_page, and wikipedia tools`

---

## SESSION 3 — Tools: file_ops & registry

**Goal:** Implement the file-writing tool and the central tool registry (schemas + dispatcher). This wires all four tools together behind a single `dispatch()` call.

**What to build:**

1. `research_agent/tools/file_ops.py` — verbatim from CLAUDE.md §7.5.
   - Import path fix: `from research_agent.config.settings import settings`

2. `research_agent/tools/registry.py` — verbatim from CLAUDE.md §7.1.
   - Import path fixes: all `from tools.X` → `from research_agent.tools.X`
   - `TOOL_SCHEMAS` list (5 schemas: `search_web`, `fetch_page`, `lookup_wikipedia`, `save_report`, `final_answer`)
   - `TOOL_FUNCTIONS` dict mapping names to callables (`final_answer` maps to `None`)
   - `dispatch(tool_name, tool_input)` function

**Acceptance test:**
```bash
python -c "
import sys; sys.path.insert(0, '.')
from research_agent.tools.registry import TOOL_SCHEMAS, dispatch

# Verify schemas loaded
print(f'{len(TOOL_SCHEMAS)} tool schemas registered')

# Verify dispatcher works for search
result = dispatch('search_web', {'query': 'test query', 'num_results': 2})
print('dispatch search_web OK, result length:', len(result))

# Verify file_ops via dispatch
result = dispatch('save_report', {'filename': 'test_report', 'content': '# Test\nHello world'})
print(result)
"
```
Expected: 5 schemas registered, search returns JSON, report saved to `reports/test_report.md`.

**Commit message:** `feat: implement file_ops tool and tool registry`

---

## SESSION 4 — Model Layer

**Goal:** Implement the Claude API client and verify a raw API call succeeds (with tools offered, no agent loop yet).

**What to build:**

1. `research_agent/models/claude_client.py` — verbatim from CLAUDE.md §6.
   - Import path fix: `from research_agent.config.settings import settings`

**Acceptance test:**
```bash
python -c "
import sys; sys.path.insert(0, '.')
from research_agent.models.claude_client import call_claude
from research_agent.tools.registry import TOOL_SCHEMAS

response = call_claude(
    messages=[{'role': 'user', 'content': 'Search for information about Python.'}],
    tools=TOOL_SCHEMAS,
    system='You are a research assistant. Use your tools to answer questions.'
)
print('stop_reason:', response.stop_reason)
print('content types:', [b.type for b in response.content])
print('Claude client OK')
"
```
Expected: `stop_reason` is either `tool_use` (Claude chose to call a tool) or `end_turn`. No API errors.

**Commit message:** `feat: implement Claude API client wrapper`

---

## SESSION 5 — Agent Layer (memory, planner, core loop)

**Goal:** Implement the three agent modules — message history manager, system prompt builder, and the ReAct loop. This is the heart of the project.

**What to build:**

1. `research_agent/agent/memory.py` — verbatim from CLAUDE.md §8.1.
   - No imports needed (pure Python class).

2. `research_agent/agent/planner.py` — verbatim from CLAUDE.md §8.2.
   - No imports needed.

3. `research_agent/agent/core.py` — verbatim from CLAUDE.md §8.3.
   - Import path fixes (all `from agent.X`, `from models.X`, `from tools.X`, `from config.X` → prefix with `research_agent.`):
     ```python
     from research_agent.agent.memory import Memory
     from research_agent.agent.planner import build_system_prompt
     from research_agent.models.claude_client import call_claude
     from research_agent.tools.registry import TOOL_SCHEMAS, dispatch
     from research_agent.config.settings import settings
     ```

**Important invariant:** After every `assistant` message containing `tool_use` blocks, the loop must call `memory.add_tool_result(tool_id, result)` for every tool call before calling Claude again. The loop in CLAUDE.md §8.3 already handles this — do not alter the structure.

**Acceptance test:**
```bash
python -c "
import sys; sys.path.insert(0, '.')
from research_agent.agent.memory import Memory
from research_agent.agent.planner import build_system_prompt

m = Memory()
m.add_user('Hello')
m.add_assistant([{'type': 'text', 'text': 'Hi there'}])
print('messages:', len(m.get()))

prompt = build_system_prompt('What is Python?')
print('system prompt length:', len(prompt))
print('Memory and planner OK')
"
```

**Commit message:** `feat: implement agent memory, planner, and ReAct core loop`

---

## SESSION 6 — Entry Point & End-to-End Test

**Goal:** Write `main.py`, run a real end-to-end research query, verify a report lands in `reports/`, then switch CLAUDE.md to slim mode per the switch condition.

**What to build:**

1. `main.py` at the project root — verbatim from CLAUDE.md §9.
   - Import path fix: `from research_agent.agent.core import run_agent`

**End-to-end test:**
```bash
cd /home/user/New-project
python main.py "What is retrieval-augmented generation and why is it useful?"
```
Watch the loop iterations print. Expected outcome:
- Several `[Tool]` and `[Result]` lines
- A `[Done]` line with a summary
- A file appears in `reports/`

**Verify the report exists:**
```bash
ls -la reports/
cat reports/*.md | head -40
```

**Switch condition check** (from CLAUDE.md top-level note):
Once the above passes — every file in §3 exists, `python main.py` runs end-to-end, and at least one report is in `reports/` — run:
```bash
mv CLAUDE.slim.md CLAUDE.md
```
Then delete the old slim file (it will have become `CLAUDE.md`).

**Commit message:** `feat: implement main.py entry point and complete end-to-end agent`

---

## Quick Reference: Import Path Rule

Every internal import across all files must use the full package path:

| CLAUDE.md shows | Actual import |
|---|---|
| `from config.settings import settings` | `from research_agent.config.settings import settings` |
| `from tools.registry import ...` | `from research_agent.tools.registry import ...` |
| `from agent.memory import Memory` | `from research_agent.agent.memory import Memory` |
| `from models.claude_client import ...` | `from research_agent.models.claude_client import ...` |

This is because `main.py` lives at the root and Python resolves `research_agent` as the top-level package.

---

## Branch

All work goes on: `claude/project-structure-plan-lBa2V`

Each session ends with:
```bash
git add <specific files>
git commit -m "feat: ..."
git push -u origin claude/project-structure-plan-lBa2V
```
