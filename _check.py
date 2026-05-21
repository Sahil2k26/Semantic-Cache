"""Diagnostic script to check all imports and identify issues."""
import traceback
import sys

print("=" * 60)
print("DIAGNOSTIC REPORT - Semantic Cache Project")
print("=" * 60)

modules_to_check = [
    ("Core Config", "from src.core.config import settings as core_settings"),
    ("Core Circuit Breaker", "from src.core.circuit_breaker import CircuitBreaker"),
    ("Core Exceptions", "from src.core.exceptions import CacheError"),
    ("Cache Base", "from src.cache.base import CacheEntry, CacheConfig, EvictionPolicy"),
    ("Cache L1", "from src.cache.l1_cache import L1Cache"),
    ("Cache L2", "from src.cache.l2_cache import L2Cache"),
    ("Cache L3", "from src.cache.l3_cache import L3Cache"),
    ("Cache Redis Config", "from src.cache.redis_config import RedisConfig"),
    ("Cache Index Manager", "from src.cache.index_manager import UnifiedIndexManager, IndexConfig"),
    ("Cache Streaming", "from src.cache.streaming import StreamingCache"),
    ("Cache Context", "from src.cache.context import SmartCacheRouter, ContextAwareCache"),
    ("Cache Manager", "from src.cache.cache_manager import CacheManager, CacheManagerConfig, CacheStrategy"),
    ("Embedding Base", "from src.embedding.base import EmbeddingProviderType"),
    ("Embedding Service", "from src.embedding.service import EmbeddingService"),
    ("Similarity Base", "from src.similarity.base import SimilarityMetric"),
    ("Similarity Service", "from src.similarity.service import SimilaritySearchService"),
    ("ML Query Parser", "from src.ml.query_parser import QueryNormalizer, RuleBasedIntentDetector"),
    ("ML Domain Classifier", "from src.ml.domain_classifier import KeyWordDomainClassifier"),
    ("ML Adaptive Thresholds", "from src.ml.adaptive_thresholds import AdaptiveThresholdManager"),
    ("Monitoring Analytics", "from src.monitoring.analytics import AnalyticsCollector"),
    ("API Config", "from src.api.config import settings"),
    ("API Auth JWT", "from src.api.auth.jwt import create_access_token, get_current_user"),
    ("API Middleware Error", "from src.api.middleware.error import add_error_handlers"),
    ("API Middleware Security", "from src.api.middleware.security import setup_security"),
    ("API Schemas", "from src.api.schemas import CacheGetResponse, HealthResponse"),
    ("API Route Health", "from src.api.routes.health import router as health_router"),
    ("API Route Admin", "from src.api.routes.admin import router as admin_router"),
    ("API Route Tenant", "from src.api.routes.tenant import router as tenant_router"),
    ("API Route Search", "from src.api.routes.search import router as search_router"),
    ("API Route Analytics", "from src.api.routes.analytics import router as analytics_router"),
    ("API Route Cache", "from src.api.routes.cache import router as cache_router"),
    ("API Main App", "from src.api.main import app"),
]

errors = []
warnings = []

for name, import_stmt in modules_to_check:
    try:
        exec(import_stmt)
        print(f"  [OK]  {name}")
    except Exception as e:
        tb = traceback.format_exc()
        errors.append((name, import_stmt, str(e), tb))
        print(f"  [ERR] {name}: {str(e)[:80]}")

print()
print("=" * 60)
print(f"SUMMARY: {len(modules_to_check) - len(errors)} OK, {len(errors)} ERRORS")
print("=" * 60)

if errors:
    print("\nDETAILED ERRORS:")
    for name, stmt, err, tb in errors:
        print(f"\n{'='*60}")
        print(f"MODULE: {name}")
        print(f"IMPORT: {stmt}")
        print(f"ERROR:  {err}")
        print(f"TRACEBACK:\n{tb}")
