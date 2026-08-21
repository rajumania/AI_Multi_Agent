import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "CampusFlow AI"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite:///./campusflow.db"
    
    # AI Configuration (centralized for later agentic steps)
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # Frontend URL for CORS
    FRONTEND_URL: str = "http://localhost:5173"
    
    # Automation Webhooks
    N8N_WEBHOOK_URL: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
