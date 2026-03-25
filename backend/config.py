
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/poker"
    SECRET_KEY: str = "change-me-in-production"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:3000"]
    JWT_EXPIRY_SECONDS: int = 3600
    PROJECT_NAME: str = "Shortdeck Holdem"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)
settings = Settings()
