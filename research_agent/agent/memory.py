class Memory:
    def __init__(self):
        self.messages: list[dict] = []

    def add_user(self, text: str):
        self.messages.append({"role": "user", "content": text})

    def add_assistant(self, content: list):
        # content is the raw list from Message.content (may include tool_use blocks)
        self.messages.append({"role": "assistant", "content": content})

    def add_tool_result(self, tool_use_id: str, result: str):
        # Tool results must be in a user message with type "tool_result"
        self.messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": result
            }]
        })

    def get(self) -> list[dict]:
        return self.messages
