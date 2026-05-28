from research_agent.config.settings import settings
from research_agent.models.provider import LLMProvider


def get_provider() -> LLMProvider:
    name = settings.provider
    if name == "anthropic":
        from research_agent.models.adapters.anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter()
    if name == "openai_compat":
        from research_agent.models.adapters.openai_adapter import OpenAICompatAdapter

        return OpenAICompatAdapter()
    raise ValueError(
        f"Unknown provider: {name!r}. Set PROVIDER to 'anthropic' or 'openai_compat'."
    )
