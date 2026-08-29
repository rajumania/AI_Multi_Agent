import os
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


_DEVELOPMENT_AUTH_SECRET = "aitam-disaster-response-ai-development-secret-key"
_DEVELOPMENT_TELEMETRY_SECRET = "campusflow-secret-telemetry-key"


class Settings(BaseSettings):
    APP_NAME: str = "AITAM Disaster Response AI"
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    CAMPUS_NAME: str = "Aditya Institute of Technology and Management (AITAM)"
    CAMPUS_LOCATION: str = "Tekkali, Srikakulam, Andhra Pradesh, India"
    CAMPUS_DEFAULT_LAT: float = 18.56517
    CAMPUS_DEFAULT_LNG: float = 84.19587
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite:///./campusflow.db"
    
    # AI Configuration
    LLM_PROVIDER: str = "gemini"
    # Bound external model calls so a provider/network stall cannot hold the
    # emergency workflow indefinitely. Existing heuristic fallback remains the
    # provider-failure path after this timeout.
    LLM_TIMEOUT_SECONDS: float = 10.0
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    # Backend-only multimodal evidence configuration.  No key is required
    # for normal operation; without one image analysis is explicit unavailable.
    VISION_PROVIDER: str = "none"
    VISION_MODEL: Optional[str] = None
    VISION_API_URL: str = "https://api.openai.com/v1/chat/completions"
    VISION_TIMEOUT_SECONDS: float = 45.0
    VISION_RETRIES: int = 1
    AUTOMATIC_AI_WORKFLOW: bool = True
    # Optional hosted Mem0 Platform memory.  It is deliberately independent
    # from the emergency workflow: missing configuration disables semantic
    # memory, it never substitutes local or fabricated memory.
    MEM0_API_KEY: Optional[str] = None
    MEM0_ORGANIZATION_ID: Optional[str] = None
    MEM0_ENABLED: bool = True
    
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
    EMAIL_FROM: Optional[str] = "emergency-alert@aitam.local"
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
    GPS_TELEMETRY_SECRET: str = ""

    # --- Authentication / RBAC (Increment 1) ---
    # Signing key for auth tokens. Default matches the legacy hardcoded key so
    # tokens minted before this change remain valid; override via env in prod.
    AUTH_SECRET_KEY: str = ""
    AUTH_TOKEN_TTL_SECONDS: int = 86400  # 24h
    # Migration flag: when True, existing command-center endpoints that predate
    # RBAC treat an unauthenticated caller as the privileged operator/admin so
    # the current single-operator UI keeps working. Set False to fully lock the
    # backend down (every protected endpoint then requires a valid token).
    ALLOW_ANONYMOUS_ADMIN: bool = False

    # Frontend URL for CORS
    FRONTEND_URL: str = "http://localhost:5173"

    # Phase 2 weather/risk configuration. Credentials stay backend-only.
    WEATHER_PROVIDER: str = "demo"
    WEATHER_API_URL: Optional[str] = "https://api.open-meteo.com/v1/forecast"
    WEATHER_API_KEY: Optional[str] = None
    WEATHER_TIMEOUT_SECONDS: float = 5.0
    WEATHER_RETRIES: int = 2
    WEATHER_RETRY_BACKOFF_SECONDS: float = 0.25
    WEATHER_STALE_AFTER_MINUTES: int = 30
    ALLOW_DETERMINISTIC_FALLBACK: bool = True
    ENVIRONMENT_PROVIDER: str = "demo"
    EARTHQUAKE_PROVIDER: str = "usgs"
    EARTHQUAKE_API_URL: str = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    EARTHQUAKE_TIMEOUT_SECONDS: float = 8.0
    EARTHQUAKE_RETRIES: int = 2
    EARTHQUAKE_RETRY_BACKOFF_SECONDS: float = 0.25
    EARTHQUAKE_STALE_AFTER_MINUTES: int = 120
    EARTHQUAKE_MIN_MAGNITUDE: float = 4.5
    EARTHQUAKE_RADIUS_KM: float = 500.0
    EARTHQUAKE_LOOKBACK_HOURS: int = 24
    # Authoritative severe-weather boundary.  IMD publishes machine-readable
    # CAP alerts through the WMO-registered feed; no cyclone is inferred from
    # community media alone.
    SEVERE_WEATHER_PROVIDER: str = "imd_cap"
    SEVERE_WEATHER_API_URL: str = "https://cap-sources.s3.amazonaws.com/in-imd-en/rss.xml"
    SEVERE_WEATHER_TIMEOUT_SECONDS: float = 8.0
    SEVERE_WEATHER_RETRIES: int = 2
    SEVERE_WEATHER_RETRY_BACKOFF_SECONDS: float = 0.25
    SEVERE_WEATHER_STALE_AFTER_MINUTES: int = 120
    SEVERE_WEATHER_RADIUS_KM: float = 150.0
    # Reverse geocoding is a best-effort label only.  Coordinates remain the
    # authoritative location used by every intelligence provider.
    GEOCODING_PROVIDER: str = "nominatim"
    GEOCODING_API_URL: str = "https://nominatim.openstreetmap.org/reverse"
    GEOCODING_TIMEOUT_SECONDS: float = 5.0
    GEOCODING_RETRIES: int = 1
    GEOCODING_RETRY_BACKOFF_SECONDS: float = 0.25
    ROUTING_TIMEOUT_SECONDS: float = 5.0
    ROUTING_RETRIES: int = 2
    ROUTING_RETRY_BACKOFF_SECONDS: float = 0.25
    SENSOR_PROVIDER: str = "demo"
    SENSOR_API_URL: Optional[str] = None
    SENSOR_API_KEY: Optional[str] = None
    SENSOR_TIMEOUT_SECONDS: float = 5.0
    SENSOR_RETRIES: int = 2
    SENSOR_RETRY_BACKOFF_SECONDS: float = 0.25
    # Uploaded evidence is stored outside frontend source and referenced by an
    # opaque ID. Local is the development implementation; object storage is a
    # future provider boundary and is never silently substituted.
    EVIDENCE_STORAGE_PROVIDER: str = "local"
    EVIDENCE_STORAGE_DIR: str = "backend/storage/evidence"
    EVIDENCE_MAX_BYTES: int = 10 * 1024 * 1024
    RISK_ALERT_COOLDOWN_MINUTES: int = 30
    RISK_THRESHOLDS_JSON: str = '{"low": 0, "medium": 25, "high": 50, "critical": 75}'
    RISK_WEIGHTS_JSON: str = '{}'
    
    # Automation Webhooks
    N8N_WEBHOOK_URL: Optional[str] = None

    # Resolve relative to this repository's backend package, not the process CWD.
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_runtime_security(self):
        environment = self.ENVIRONMENT.strip().lower()
        production = environment in {"production", "prod"}
        if "aitam.db" in self.DATABASE_URL.lower():
            raise ValueError("DATABASE_URL must not point to aitam.db; use campusflow.db or an approved deployment database.")
        if production:
            if not self.AUTH_SECRET_KEY or self.AUTH_SECRET_KEY == _DEVELOPMENT_AUTH_SECRET:
                raise ValueError("AUTH_SECRET_KEY must be set to a unique production secret.")
            if not self.GPS_TELEMETRY_SECRET or self.GPS_TELEMETRY_SECRET == _DEVELOPMENT_TELEMETRY_SECRET:
                raise ValueError("GPS_TELEMETRY_SECRET must be set to a unique production secret.")
            if self.ALLOW_ANONYMOUS_ADMIN:
                raise ValueError("ALLOW_ANONYMOUS_ADMIN must be false in production.")
            if not self.FRONTEND_URL.strip() or self.FRONTEND_URL.strip() == "*":
                raise ValueError("FRONTEND_URL must be an explicit production origin.")
            if self.EVIDENCE_STORAGE_PROVIDER.strip().lower() == "local":
                raise ValueError("Local evidence storage is development-only; configure an approved production storage provider.")
        else:
            if not self.AUTH_SECRET_KEY:
                self.AUTH_SECRET_KEY = _DEVELOPMENT_AUTH_SECRET
            if not self.GPS_TELEMETRY_SECRET:
                self.GPS_TELEMETRY_SECRET = _DEVELOPMENT_TELEMETRY_SECRET
        return self


settings = Settings()

