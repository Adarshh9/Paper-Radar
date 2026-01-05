"""
Application configuration using Pydantic Settings.
Production-grade configuration with validation.
"""
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Application
    app_name: str = "Paper Radar"
    environment: str = Field(default="development", pattern="^(development|staging|production)$")
    debug: bool = False
    
    # Database
    database_url: str = Field(
        default="postgresql://user:password@localhost:5432/paperradar",
        description="PostgreSQL connection URL",
    )
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=100)
    
    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL",
    )
    
    # API Keys
    groq_api_key: str = Field(default="", description="Groq API key for LLM summaries")
    github_token: str = Field(default="", description="GitHub Personal Access Token")
    
    # Security
    secret_key: str = Field(
        default="change-this-to-a-secure-random-key-in-production",
        min_length=32,
        description="Secret key for JWT encoding",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=1440, ge=1)  # 24 hours
    
    # CORS
    cors_origins: str = "http://localhost:3000"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    # Rate Limiting
    arxiv_requests_per_second: float = Field(default=2.5, ge=0.1, le=10.0)
    semantic_scholar_requests_per_5min: int = Field(default=100, ge=1)
    groq_requests_per_minute: int = Field(default=30, ge=1)
    
    # Categories to track
    arxiv_categories: List[str] = [
        "cs.AI", "cs.LG", "cs.CV", "cs.CL", "cs.NE", "stat.ML"
    ]
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
