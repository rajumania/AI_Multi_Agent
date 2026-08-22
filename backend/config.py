import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "CampusFlow AI"
    CAMPUS_NAME: str = "Vignan's Foundation for Science, Technology & Research (VFSTR - Vignan University)"
    CAMPUS_LOCATION: str = "Vadlamudi, Guntur - 522213, Andhra Pradesh, India"
    CAMPUS_DEFAULT_LAT: float = 16.2334
    CAMPUS_DEFAULT_LNG: float = 80.5513
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite:///./campusflow.db"
    
    # AI Configuration
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # Map & Routing Providers
    MAP_PROVIDER: str = "esri_satellite"
    MAP_API_KEY: Optional[str] = None
    ROUTING_PROVIDER: str = "osrm"
    ROUTING_API_KEY: Optional[str] = None
    ROUTING_BASE_URL: str = "http://router.project-osrm.org"

    # SMS Provider
    SMS_PROVIDER: Optional[str] = None  # e.g., 'twilio'
    SMS_ACCOUNT_ID: Optional[str] = None
    SMS_AUTH_TOKEN: Optional[str] = None
    SMS_API_KEY_SID: Optional[str] = None
    SMS_API_KEY_SECRET: Optional[str] = None
    SMS_FROM_NUMBER: Optional[str] = None
    TEST_PHONE_NUMBER: Optional[str] = None


    # Push Notification Provider
    PUSH_PROVIDER: Optional[str] = None  # e.g., 'fcm'
    PUSH_CREDENTIALS: Optional[str] = None
    TEST_DEVICE_TOKEN: Optional[str] = None

    # Email SMTP Provider
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: Optional[str] = "emergency-alert@vignan.ac.in"
    TEST_EMAIL_ADDRESS: Optional[str] = None

    # Voice & Telephony Provider
    VOICE_PROVIDER: Optional[str] = None  # e.g., 'twilio'
    VOICE_ACCOUNT_ID: Optional[str] = None
    VOICE_AUTH_TOKEN: Optional[str] = None
    VOICE_FROM_NUMBER: Optional[str] = None
    TEST_VOICE_NUMBER: Optional[str] = None

    # Dispatch Integration API
    DISPATCH_PROVIDER: Optional[str] = None  # e.g., 'campus_dispatch_webhook'
    DISPATCH_API_URL: Optional[str] = None
    DISPATCH_API_TOKEN: Optional[str] = None


    # GPS Telemetry Auth Secret
    GPS_TELEMETRY_SECRET: str = "campusflow-secret-telemetry-key"
    
    # Frontend URL for CORS
    FRONTEND_URL: str = "http://localhost:5173"
    
    # Automation Webhooks
    N8N_WEBHOOK_URL: Optional[str] = None

    # Resolve relative to this repository's backend package, not the process CWD.
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        extra="ignore",
    )


settings = Settings()

