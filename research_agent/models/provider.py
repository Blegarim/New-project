from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass
class ContentBlock:
    """One block in an assistant response, in canonical (Anthropic-style) form."""

    type: Literal["text", "tool_use"]
    text: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict | None = None

    def to_dict(self) -> dict:
        if self.type == "text":
            return {"type": "text", "text": self.text}
        if self.type == "tool_use":
            return {
                "type": "tool_use",
                "id": self.id,
                "name": self.name,
                "input": self.input or {},
            }
        raise ValueError(f"Unknown block type: {self.type}")


@dataclass
class NormalizedResponse:
    stop_reason: Literal["tool_use", "end_turn", "max_tokens", "stop_sequence", "stop"]
    content: list[ContentBlock]
    raw: Any = None


class LLMProvider(Protocol):
    """Plug-and-play interface for LLM backends.

    All providers accept canonical (Anthropic-style) messages and tool schemas,
    and return a NormalizedResponse with provider-agnostic content blocks.
    Adapters own the translation in and out of provider-native formats.
    """

    def call(
        self, messages: list[dict], tools: list[dict], system: str
    ) -> NormalizedResponse: ...
