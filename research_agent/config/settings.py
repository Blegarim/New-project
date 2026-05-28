from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 4096
    max_loop_iterations: int = 10    # safety cap on the ReAct loop
    reports_dir: str = "reports"
    jina_base_url: str = "https://r.jina.ai/"

    class Config:
        env_file = ".env"

settings = Settings()
