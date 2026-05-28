import inspect

from research_agent.tools.search import search_web
from research_agent.tools.fetch_page import fetch_page
from research_agent.tools.wikipedia import lookup_wikipedia
from research_agent.tools.file_ops import save_report

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
    params = inspect.signature(fn).parameters
    kwargs = {k: v for k, v in tool_input.items() if k in params}
    return fn(**kwargs)
