from duckduckgo_search import DDGS
import json

def search_web(query: str, num_results: int = 5) -> str:
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=num_results):
                results.append({
                    "title": r.get("title"),
                    "url": r.get("href"),
                    "snippet": r.get("body")
                })
        return json.dumps(results, indent=2)
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})
