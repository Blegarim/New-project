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
