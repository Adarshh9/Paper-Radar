"""
Application configuration using Pydantic Settings.
Production-grade configuration with validation.
"""
from functools import lru_cache
from pathlib import Path
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
    
    # Local development mode - uses SQLite and file cache instead of PostgreSQL/Redis
    use_local_storage: bool = Field(
        default=True,
        description="Use SQLite and file-based cache for local development",
    )
    local_data_dir: str = Field(
        default="./data",
        description="Directory for local data storage (SQLite db, cache files)",
    )
    
    # Database
    database_url: str = Field(
        default="postgresql://user:password@localhost:5432/paperradar",
        description="PostgreSQL connection URL (used when use_local_storage=False)",
    )
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=100)
    
    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL (used when use_local_storage=False)",
    )
    
    # API Keys
    groq_api_key: str = Field(default="", description="Groq API key for LLM summaries")
    github_token: str = Field(default="", description="GitHub Personal Access Token")
    semantic_scholar_api_key: str = Field(default="", description="Semantic Scholar API key (optional, increases rate limits)")
    
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
    
    # Rate Limiting (more conservative defaults for local dev)
    arxiv_requests_per_second: float = Field(default=2.0, ge=0.1, le=10.0)
    semantic_scholar_requests_per_5min: int = Field(default=80, ge=1)  # Conservative limit
    groq_requests_per_minute: int = Field(default=30, ge=1)
    
    # Categories to track - expanded to cover more research areas
    arxiv_categories: List[str] = [
        # Core AI/ML
        "cs.AI",   # Artificial Intelligence
        "cs.LG",   # Machine Learning
        "cs.CV",   # Computer Vision
        "cs.CL",   # Computation and Language (NLP)
        "cs.NE",   # Neural and Evolutionary Computing
        "stat.ML", # Statistics - Machine Learning
        
        # Related CS fields
        "cs.RO",   # Robotics
        "cs.HC",   # Human-Computer Interaction
        "cs.IR",   # Information Retrieval
        "cs.SE",   # Software Engineering
        "cs.CR",   # Cryptography and Security
        "cs.DC",   # Distributed Computing
        "cs.DB",   # Databases
        "cs.PL",   # Programming Languages
        
        # Emerging areas
        "cs.MA",   # Multiagent Systems
        "cs.SI",   # Social and Information Networks
        "cs.CY",   # Computers and Society
        "cs.GT",   # Computer Science and Game Theory
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
    
    @property
    def data_directory(self) -> Path:
        """Get the local data directory path."""
        path = Path(self.local_data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def sqlite_database_url(self) -> str:
        """Get SQLite database URL for local development."""
        db_path = self.data_directory / "paperradar.db"
        return f"sqlite:///{db_path}"
    
    @property
    def effective_database_url(self) -> str:
        """Get the database URL based on storage mode."""
        if self.use_local_storage:
            return self.sqlite_database_url
        return self.database_url


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
