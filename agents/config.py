import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class AgentSettings(BaseSettings):
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    DEFAULT_MODEL: str = "gemini-1.5-pro"
    FALLBACK_MODEL: str = "gemini-1.5-flash"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

agent_settings = AgentSettings()
