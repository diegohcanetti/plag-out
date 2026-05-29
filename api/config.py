import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # API key for frontend authentication
    plagout_api_key: str = Field("plagout_secret_token_123", validation_alias="PLAGOUT_API_KEY")
    
    # Database connection URL
    database_url: str = Field("postgresql://localhost/plagout_db", validation_alias="DATABASE_URL")
    
    # Application Defaults
    default_pagination_limit: int = Field(50, validation_alias="DEFAULT_PAGINATION_LIMIT")
    default_geospatial_radius_km: float = Field(5.0, validation_alias="DEFAULT_GEOSPATIAL_RADIUS_KM")

    # Load configuration from environment or .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
