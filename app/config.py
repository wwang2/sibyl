"""Configuration management using Pydantic Settings."""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Database
    db_url: str = Field(default="sqlite:///./local.db", env="DB_URL")
    
    # Google AI
    google_api_key: str = Field(default="dummy_key", env="GOOGLE_API_KEY")
    model: str = Field(default="gemini-1.5-flash", env="MODEL")
    
    # Sources
    sources: List[str] = Field(default=["rss"], env="SOURCES")
    
    # Run mode
    run_mode: str = Field(default="local", env="RUN_MODE")
    
    # LLM mode
    llm_mode: str = Field(default="live", env="LLM_MODE")  # live | mock
    mock_seed: int = Field(default=42, env="MOCK_SEED")
    
    # RSS fixture for testing
    rss_fixture: str = Field(default="", env="RSS_FIXTURE")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
