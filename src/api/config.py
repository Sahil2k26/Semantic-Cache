"""Configuration for FastAPI application."""

from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    """Application settings."""
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8001
    API_RELOAD: bool = False
    API_WORKERS: int = 4
    
    # Environment
    ENVIRONMENT: str = "development"  # development, testing, production
    LOG_LEVEL: str = "INFO"
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/cache_db"
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    
    # JWT Authentication
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Cache Configuration
    L1_MAX_SIZE: int = 10000  # Max entries in L1 cache
    L1_EVICTION_STRATEGY: str = "LRU"  # LRU, LFU, FIFO
    L1_TTL_SECONDS: int = 3600  # Time to live for L1 cache
    
    L2_MAX_CAPACITY: int = 100000
    CACHE_STRATEGY: str = "write_through"  # write_through, write_back, l1_only, l2_only
    ENABLE_L1_TO_L2_PROMOTION: bool = True  # Promote L2 hits to L1
    ENABLE_L2_COMPRESSION: bool = True  # Enable compression in L2
    
    # Embedding Service
    EMBEDDING_PROVIDER: str = "openai"  # openai, huggingface, local
    OPENAI_API_KEY: str = ""
    HUGGINGFACE_API_KEY: str = ""
    
    # LLM Service
    LLM_PROVIDER: str = "gemini"  # gemini, openai
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gemini-pro"
    
    # Performance
    CONNECTION_POOL_SIZE: int = 20
    BATCH_SIZE: int = 20
    COMPRESSION_ENABLED: bool = True
    
    # Feature Flags
    DEDUPLICATION_ENABLED: bool = True
    COST_AWARE_EVICTION_ENABLED: bool = True
    PREDICTIVE_PREFETCH_ENABLED: bool = True
    MULTI_TENANCY_ENABLED: bool = True
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 10000
    RATE_LIMIT_PERIOD_SECONDS: int = 60
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
