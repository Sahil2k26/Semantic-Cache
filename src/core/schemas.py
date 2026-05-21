"""
Pydantic schemas for API request/response validation.

Defines data validation models for all API endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# ===== Embedding-related schemas =====

class EmbeddingVector(BaseModel):
    """Schema for embedding vectors."""

    values: List[float] = Field(..., description="Vector values")
    dimension: int = Field(..., description="Vector dimension")
    model: str = Field(..., description="Embedding model used")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "values": [0.1, 0.2, 0.3],
                "dimension": 3,
                "model": "sentence-transformers/all-MiniLM-L6-v2",
            }
        }


# ===== Cache query schemas =====

class QueryRequest(BaseModel):
    """Schema for cache query requests."""

    query_text: str = Field(..., min_length=1, description="Query text to cache")
    tenant_id: str = Field(..., description="Tenant ID")
    user_id: Optional[str] = Field(default=None, description="User ID for tracking")
    
    # Optional context
    domain: Optional[str] = Field(
        default=None,
        description="Domain hint (medical, legal, ecommerce, general)",
    )
    metadata: Optional[Dict[str, str]] = Field(
        default=None, description="Additional metadata for filtering"
    )
    
    # Similarity control
    similarity_threshold: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Override default similarity threshold"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query_text": "What is machine learning?",
                "tenant_id": "tenant_123",
                "user_id": "user_456",
                "domain": "general",
                "similarity_threshold": 0.85,
            }
        }


class CacheResponse(BaseModel):
    """Schema for cache query responses."""

    response_text: str = Field(..., description="Cached or generated response")
    is_cached: bool = Field(..., description="Whether response came from cache")
    cache_level: Optional[str] = Field(
        default=None, description="Cache level if hit (L1, L2, L3)"
    )
    
    # Similarity details
    similarity_score: Optional[float] = Field(
        default=None, description="Similarity score if from cache"
    )
    original_query: Optional[str] = Field(
        default=None, description="Original cached query if similar match"
    )
    
    # Metadata
    latency_ms: float = Field(..., description="Response latency in milliseconds")
    processing_time_ms: float = Field(
        ..., description="Total processing time in milliseconds"
    )
    
    # Cost info
    cost_saved: Optional[float] = Field(
        default=None, description="Estimated cost saved by cache hit"
    )
    
    # Tracing
    request_id: Optional[str] = Field(
        default=None, description="Request ID for tracing"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "response_text": "Machine learning is a subset of AI...",
                "is_cached": True,
                "cache_level": "L1",
                "similarity_score": 0.92,
                "original_query": "What is ML?",
                "latency_ms": 2.5,
                "processing_time_ms": 15.3,
                "cost_saved": 0.002,
            }
        }


# ===== Cache statistics schemas =====

class CacheStats(BaseModel):
    """Schema for cache statistics."""

    total_queries: int = Field(..., description="Total number of queries")
    cache_hits: int = Field(..., description="Number of cache hits")
    cache_misses: int = Field(..., description="Number of cache misses")
    hit_rate: float = Field(..., ge=0.0, le=1.0, description="Cache hit rate (0-1)")
    
    # Performance
    avg_latency_ms: float = Field(
        ..., description="Average query latency in milliseconds"
    )
    p95_latency_ms: float = Field(
        ..., description="95th percentile latency in milliseconds"
    )
    p99_latency_ms: float = Field(
        ..., description="99th percentile latency in milliseconds"
    )
    
    # Capacity
    total_cached_entries: int = Field(..., description="Number of cached entries")
    l1_entries: int = Field(..., description="Number of L1 cache entries")
    l2_entries: int = Field(..., description="Number of L2 cache entries")
    l3_entries: int = Field(default=0, description="Number of L3 cache entries")
    
    # Cost
    total_cost_saved: float = Field(
        ..., description="Total cost saved by cache hits"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_queries": 1000,
                "cache_hits": 620,
                "cache_misses": 380,
                "hit_rate": 0.62,
                "avg_latency_ms": 25.5,
                "p95_latency_ms": 45.3,
                "p99_latency_ms": 95.2,
                "total_cached_entries": 5000,
                "l1_entries": 3000,
                "l2_entries": 2000,
                "total_cost_saved": 150.50,
            }
        }


# ===== Health check schemas =====

class HealthCheckResponse(BaseModel):
    """Schema for health check response."""

    status: str = Field(..., description="Overall health status (healthy, degraded, unhealthy)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(..., description="Service version")
    
    # Component health
    components: Dict[str, str] = Field(
        ..., description="Health status of individual components"
    )
    
    # Details
    message: Optional[str] = Field(default=None, description="Additional health message")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-03-18T10:30:00Z",
                "version": "0.1.0",
                "components": {
                    "database": "healthy",
                    "redis": "healthy",
                    "embedding_service": "healthy",
                },
                "message": "All systems operational",
            }
        }


class ComponentStatus(BaseModel):
    """Schema for individual component status."""

    name: str = Field(..., description="Component name")
    status: str = Field(..., description="Status (healthy, degraded, unhealthy)")
    details: Optional[Dict[str, Any]] = Field(default=None)
    last_check: datetime = Field(default_factory=datetime.utcnow)


# ===== Error response schemas =====

class ErrorResponse(BaseModel):
    """Schema for error responses."""

    error_code: str = Field(..., description="Error code for programmatic handling")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    request_id: Optional[str] = Field(default=None, description="Request ID for debugging")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "error_code": "EMBEDDING_ERROR",
                "message": "Failed to generate embedding: Timeout",
                "details": {"provider": "openai", "retry_after": 60},
                "request_id": "req_12345",
                "timestamp": "2024-03-18T10:30:00Z",
            }
        }


# ===== Tenant schemas =====

class TenantCreate(BaseModel):
    """Schema for creating a new tenant."""

    id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None)
    
    # Quotas
    max_cache_entries: int = Field(default=100000, ge=1000)
    max_qps: int = Field(default=1000, ge=10)
    max_storage_gb: float = Field(default=10.0, ge=1.0)


class TenantUpdate(BaseModel):
    """Schema for updating tenant."""

    name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    max_cache_entries: Optional[int] = Field(default=None)
    max_qps: Optional[int] = Field(default=None)
    max_storage_gb: Optional[float] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)


class TenantInfo(BaseModel):
    """Schema for tenant information."""

    id: str
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    # Quotas
    max_cache_entries: int
    max_qps: int
    max_storage_gb: float
    
    # Usage
    current_entries: int = Field(default=0)
    current_qps: float = Field(default=0.0)
    current_storage_gb: float = Field(default=0.0)

    class Config:
        from_attributes = True


# ===== Configuration schemas =====

class CacheConfig(BaseModel):
    """Schema for cache configuration."""

    l1_max_entries: int = Field(default=100000)
    l2_max_entries: int = Field(default=1000000)
    l3_max_entries: int = Field(default=10000000)
    
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    embedding_dimension: int = Field(default=384)
    
    similarity_metric: str = Field(default="cosine")
    default_similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    
    database_url: str = Field(...)


# ===== Domain classification schemas =====

class DomainClassificationResult(BaseModel):
    """Schema for domain classification results."""

    query_text: str = Field(..., description="Original query")
    predicted_domain: str = Field(..., description="Predicted domain")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    similarity_threshold: float = Field(..., description="Recommended threshold for domain")

    class Config:
        json_schema_extra = {
            "example": {
                "query_text": "What are contraindications for aspirin use?",
                "predicted_domain": "medical",
                "confidence": 0.945,
                "similarity_threshold": 0.95,
            }
        }


# ===== API response pagination =====

class PaginatedResponse(BaseModel):
    """Schema for paginated responses."""

    items: List[Any] = Field(..., description="Response items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")

    @field_validator("total_pages", mode="before")
    @classmethod
    def calculate_total_pages(cls, v, info):
        """Calculate total pages from total and page_size."""
        data = info.data if hasattr(info, "data") else {}
        if "total" in data and "page_size" in data and data["page_size"] > 0:
            return (data["total"] + data["page_size"] - 1) // data["page_size"]
        return v


# ===== Cache entry schema (used by internal imports) =====

class CacheEntrySchema(BaseModel):
    """Schema representing a single cached entry — used internally for serialization."""

    query_id: str = Field(..., description="Unique query identifier")
    query_text: str = Field(..., description="Original query text")
    response: Optional[Any] = Field(default=None, description="Cached response")
    domain: str = Field(default="general", description="Domain classification")
    similarity_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    cache_level: Optional[str] = Field(default=None, description="Cache tier (L1/L2/L3)")
    created_at: Optional[datetime] = Field(default=None)
    access_count: int = Field(default=0, ge=0)

    class Config:
        json_schema_extra = {
            "example": {
                "query_id": "abc123",
                "query_text": "What is machine learning?",
                "response": "ML is a subset of AI...",
                "domain": "general",
                "similarity_score": 0.92,
                "cache_level": "L1",
                "access_count": 5,
            }
        }
