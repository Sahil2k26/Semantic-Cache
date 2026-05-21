"""Pydantic schemas for API requests/responses."""

from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime

# ==================== Cache Operations ====================

class CacheGetResponse(BaseModel):
    """Response for GET cache operation."""
    key: str
    value: Optional[Any] = None
    hit: bool
    cache_level: Optional[str] = None
    latency_ms: float = 0.0
    ttl_remaining_seconds: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "key": "my_key",
                "value": "cached_value",
                "hit": True,
                "cache_level": "l1",
                "latency_ms": 0.5,
                "ttl_remaining_seconds": 3599
            }
        }


class CachePutRequest(BaseModel):
    """Request for PUT cache operation."""
    value: Any
    ttl_seconds: Optional[int] = None
    cost: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "value": "some_value",
                "ttl_seconds": 3600,
                "cost": 100,
                "metadata": {"domain": "embedding"}
            }
        }


class CachePutResponse(BaseModel):
    """Response for PUT cache operation."""
    key: str
    cached: bool
    cache_level: str
    size_bytes: int

    class Config:
        json_schema_extra = {
            "example": {
                "key": "my_key",
                "cached": True,
                "cache_level": "l2",
                "size_bytes": 125
            }
        }


class CacheBatchRequest(BaseModel):
    """Request for batch cache operations."""
    keys: List[str] = Field(..., min_length=1, max_length=100)

    class Config:
        json_schema_extra = {
            "example": {
                "keys": ["key1", "key2", "key3"]
            }
        }


class CacheBatchResult(BaseModel):
    """Single result in batch response."""
    key: str
    value: Optional[Any] = None
    hit: bool


class CacheBatchResponse(BaseModel):
    """Response for batch cache operations."""
    results: List[CacheBatchResult]
    hit_count: int
    miss_count: int
    hit_rate: float

    class Config:
        json_schema_extra = {
            "example": {
                "results": [
                    {"key": "key1", "value": "val1", "hit": True},
                    {"key": "key2", "value": None, "hit": False}
                ],
                "hit_count": 1,
                "miss_count": 1,
                "hit_rate": 0.5
            }
        }


# ==================== Search ====================

class SearchRequest(BaseModel):
    """Request for similarity search."""
    query: str
    top_k: int = 5
    threshold: float = 0.8
    metric: str = "cosine"  # cosine, euclidean, manhattan, hamming, jaccard

    class Config:
        json_schema_extra = {
            "example": {
                "query": "what is machine learning",
                "top_k": 5,
                "threshold": 0.8,
                "metric": "cosine"
            }
        }


class SearchResult(BaseModel):
    """Single result in search response."""
    key: str
    similarity: float
    value: Optional[Any] = None
    cache_level: str


class SearchResponse(BaseModel):
    """Response for similarity search."""
    query: str
    metric: str
    results: List[SearchResult]
    count: int
    search_time_ms: Optional[float] = None

    class Config:
        json_schema_extra = {
            "example": {
                "query": "what is machine learning",
                "metric": "cosine",
                "results": [
                    {
                        "key": "ml_primer_1",
                        "similarity": 0.95,
                        "value": "cached_result",
                        "cache_level": "l1"
                    }
                ],
                "count": 1,
                "search_time_ms": 125.3
            }
        }


# ==================== Deduplication ====================

class DedupRegisterRequest(BaseModel):
    """Request for query deduplication registration."""
    query: str
    strategy: str = "normalized"  # exact, normalized, semantic, prefix

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What is AI?",
                "strategy": "normalized"
            }
        }


class DedupRegisterResponse(BaseModel):
    """Response for deduplication registration."""
    canonical: str
    is_duplicate: bool
    strategy: str

    class Config:
        json_schema_extra = {
            "example": {
                "canonical": "what is ai",
                "is_duplicate": False,
                "strategy": "normalized"
            }
        }


class DedupStatsResponse(BaseModel):
    """Response for deduplication statistics."""
    total_deduplicated: int
    unique_queries: int
    reduction_percentage: float
    top_duplicates: List[Dict[str, Any]]

    class Config:
        json_schema_extra = {
            "example": {
                "total_deduplicated": 245,
                "unique_queries": 123,
                "reduction_percentage": 49.8,
                "top_duplicates": [
                    {"canonical": "what is ai", "count": 15}
                ]
            }
        }


# ==================== Admin ====================

class AdminStatsResponse(BaseModel):
    """Response for admin statistics."""
    total_items_cached: int
    total_memory_mb: float
    l1_capacity_pct: float
    l2_capacity_pct: float
    hit_rate_overall: float
    requests_today: int
    unique_users: int

    class Config:
        json_schema_extra = {
            "example": {
                "total_items_cached": 50000,
                "total_memory_mb": 512,
                "l1_capacity_pct": 75,
                "l2_capacity_pct": 45,
                "hit_rate_overall": 0.82,
                "requests_today": 150000,
                "unique_users": 1234
            }
        }


class OptimizeRequest(BaseModel):
    """Request for cache optimization."""
    strategy: str = "balanced"  # conservative, balanced, aggressive
    dry_run: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "strategy": "aggressive",
                "dry_run": False
            }
        }


class OptimizeResponse(BaseModel):
    """Response for cache optimization."""
    status: str
    items_evicted: int
    memory_freed_mb: float
    new_hit_rate: float

    class Config:
        json_schema_extra = {
            "example": {
                "status": "completed",
                "items_evicted": 234,
                "memory_freed_mb": 45,
                "new_hit_rate": 0.87
            }
        }


# ==================== Health ====================

class ServiceStatus(BaseModel):
    """Status of a single service."""
    name: str
    status: str
    message: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    cache_level: str
    redis: str
    postgres: str
    uptime_seconds: int

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "cache_level": "l2",
                "redis": "connected",
                "postgres": "connected",
                "uptime_seconds": 3600
            }
        }


class HealthDetailedResponse(BaseModel):
    """Detailed health check response."""
    status: str
    services: Dict[str, str]
    metrics: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "services": {
                    "cache_l1": "operational",
                    "cache_l2": "operational",
                    "redis": "connected",
                    "postgres": "healthy"
                },
                "metrics": {
                    "cache_hit_rate": 0.85,
                    "avg_latency_ms": 5.2,
                    "memory_used_mb": 256
                }
            }
        }


# ==================== Multi-Tenant ====================

class TenantQuotaRequest(BaseModel):
    """Request for creating/updating tenant quota."""
    tenant_id: str
    quota_memory_mb: int
    quota_queries_daily: int
    quota_request_size_kb: int

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "acme_corp",
                "quota_memory_mb": 1000,
                "quota_queries_daily": 100000,
                "quota_request_size_kb": 500
            }
        }


class TenantMetricsResponse(BaseModel):
    """Response for tenant metrics."""
    tenant_id: str
    memory_used_mb: float
    memory_quota_mb: int
    queries_today: int
    queries_quota: int
    hit_rate: float

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "acme_corp",
                "memory_used_mb": 250,
                "memory_quota_mb": 1000,
                "queries_today": 45000,
                "queries_quota": 100000,
                "hit_rate": 0.88
            }
        }


# ==================== Error ====================

class ErrorDetail(BaseModel):
    """Error detail information."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = False
    error: ErrorDetail
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": {
                    "code": "CACHE_NOT_FOUND",
                    "message": "Key not found in cache",
                    "details": {}
                },
                "timestamp": "2026-03-18T10:30:00Z"
            }
        }
