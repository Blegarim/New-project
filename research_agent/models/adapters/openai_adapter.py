import json

from research_agent.config.settings import settings
from research_agent.models.provider import ContentBlock, NormalizedResponse


class OpenAICompatAdapter:
    """Adapter for any OpenAI-compatible Chat Completions endpoint.

    Works with: OpenAI, Groq, Cerebras, OpenRouter, Together, Fireworks,
    Ollama (local), and others. Configure via BASE_URL + OPENAI_API_KEY.
    """

    def __init__(self) -> None:
        from openai import OpenAI

        self.client = OpenAI(
            api_key=settings.openai_api_key or "not-needed",
            base_url=settings.base_url or None,
        )

    def call(
        self, messages: list[dict], tools: list[dict], system: str
    ) -> NormalizedResponse:
        oai_messages = [{"role": "system", "content": system}]
        oai_messages.extend(self._translate_messages(messages))
        oai_tools = [self._translate_tool(t) for t in tools]

        response = self.client.chat.completions.create(
            model=settings.model,
            max_tokens=settings.max_tokens,
            messages=oai_messages,
            tools=oai_tools,
            tool_choice="auto",
        )
        choice = response.choices[0]
        msg = choice.message

        blocks: list[ContentBlock] = []
        if msg.content:
            blocks.append(ContentBlock(type="text", text=msg.content))
        for tc in msg.tool_calls or []:
            blocks.append(
                ContentBlock(
                    type="tool_use",
                    id=tc.id,
                    name=tc.function.name,
                    input=json.loads(tc.function.arguments or "{}"),
                )
            )

        stop_reason = "tool_use" if choice.finish_reason == "tool_calls" else "end_turn"
        return NormalizedResponse(stop_reason=stop_reason, content=blocks, raw=response)

    @staticmethod
    def _translate_tool(tool: dict) -> dict:
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }

    @staticmethod
    def _translate_messages(messages: list[dict]) -> list[dict]:
        out: list[dict] = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "user":
                if isinstance(content, str):
                    out.append({"role": "user", "content": content})
                    continue
                for block in content:
                    btype = block.get("type")
                    if btype == "tool_result":
                        result = block.get("content", "")
                        if not isinstance(result, str):
                            result = json.dumps(result)
                        out.append(
                            {
                                "role": "tool",
                                "tool_call_id": block["tool_use_id"],
                                "content": result,
                            }
                        )
                    elif btype == "text":
                        out.append({"role": "user", "content": block["text"]})

            elif role == "assistant":
                text_parts: list[str] = []
                tool_calls: list[dict] = []
                if isinstance(content, str):
                    text_parts.append(content)
                else:
                    for block in content:
                        btype = block.get("type")
                        if btype == "text":
                            text_parts.append(block.get("text", ""))
                        elif btype == "tool_use":
                            tool_calls.append(
                                {
                                    "id": block["id"],
                                    "type": "function",
                                    "function": {
                                        "name": block["name"],
                                        "arguments": json.dumps(block.get("input") or {}),
                                    },
                                }
                            )
                assistant_msg: dict = {"role": "assistant"}
                joined = "\n".join(p for p in text_parts if p)
                assistant_msg["content"] = joined or None
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                out.append(assistant_msg)
        return out
