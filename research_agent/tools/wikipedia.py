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
