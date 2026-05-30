import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # API key for frontend authentication
    plagout_api_key: str = Field(..., validation_alias="PLAGOUT_API_KEY", description="Secret API Key")
    
    # Database connection URL (Default is for local dev only)
    database_url: str = Field(..., validation_alias="DATABASE_URL")
    
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
