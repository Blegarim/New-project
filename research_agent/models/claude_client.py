# STATUS (Session 4):
#   - Module written per CLAUDE.md §6 and imports cleanly with anthropic==0.104.1.
#   - NOT YET VERIFIED: the live acceptance test (real API call with TOOL_SCHEMAS)
#     was not run because no ANTHROPIC_API_KEY was available in the build env.
#
# TODO (run locally before relying on this client):
#   1. Set ANTHROPIC_API_KEY in .env (see .env.example).
#   2. Run the acceptance snippet from Session 4 and confirm:
#        - response.stop_reason is "tool_use" or "end_turn"
#        - no API/auth errors
#   3. If the call fails with a 404/model error, double-check
#      settings.model ("claude-haiku-4-5-20251001") is still a valid model ID.

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
