from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    provider: Literal["anthropic", "openai_compat"] = "anthropic"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    base_url: str | None = None

    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 4096
    max_loop_iterations: int = 10
    reports_dir: str = "reports"
    jina_base_url: str = "https://r.jina.ai/"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
