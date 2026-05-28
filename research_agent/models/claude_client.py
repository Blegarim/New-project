import anthropic
from research_agent.config.settings import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

def call_claude(messages: list[dict], tools: list[dict], system: str) -> anthropic.types.Message:
    return client.messages.create(
        model=settings.model,
        max_tokens=settings.max_tokens,
        system=system,
        tools=tools,
        messages=messages,
    )
