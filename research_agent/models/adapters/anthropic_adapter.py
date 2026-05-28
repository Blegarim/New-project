import anthropic

from research_agent.config.settings import settings
from research_agent.models.provider import ContentBlock, NormalizedResponse


class AnthropicAdapter:
    """Native Anthropic adapter. Canonical format matches the wire format,
    so messages and tools pass through unchanged."""

    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Add it to .env or switch PROVIDER."
            )
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def call(
        self, messages: list[dict], tools: list[dict], system: str
    ) -> NormalizedResponse:
        response = self.client.messages.create(
            model=settings.model,
            max_tokens=settings.max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )
        blocks: list[ContentBlock] = []
        for b in response.content:
            if b.type == "text":
                blocks.append(ContentBlock(type="text", text=b.text))
            elif b.type == "tool_use":
                blocks.append(
                    ContentBlock(
                        type="tool_use",
                        id=b.id,
                        name=b.name,
                        input=dict(b.input) if b.input else {},
                    )
                )
        return NormalizedResponse(
            stop_reason=response.stop_reason,
            content=blocks,
            raw=response,
        )
