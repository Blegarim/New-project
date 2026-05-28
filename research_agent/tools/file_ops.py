import os
from research_agent.config.settings import settings

def save_report(filename: str, content: str) -> str:
    os.makedirs(settings.reports_dir, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in filename)
    path = os.path.join(settings.reports_dir, safe_name + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Report saved to: {path}"
