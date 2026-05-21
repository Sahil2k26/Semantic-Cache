import traceback, sys, os

results = []

checks = [
    ("core.config",           "from src.core.config import settings as core_settings"),
    ("core.circuit_breaker",  "from src.core.circuit_breaker import CircuitBreaker"),
    ("core.exceptions",       "from src.core.exceptions import CacheError"),
    ("core.models",           "from src.core.models import Base"),
    ("core.schemas",          "from src.core.schemas import CacheEntrySchema"),
    ("core.database",         "from src.core.database import DatabaseManager"),
    ("cache.base",            "from src.cache.base import CacheEntry, CacheConfig, EvictionPolicy"),
    ("cache.l1_cache",        "from src.cache.l1_cache import L1Cache"),
    ("cache.l2_cache",        "from src.cache.l2_cache import L2Cache"),
    ("cache.l3_cache",        "from src.cache.l3_cache import L3Cache"),
    ("cache.redis_config",    "from src.cache.redis_config import RedisConfig"),
    ("cache.index_manager",   "from src.cache.index_manager import UnifiedIndexManager, IndexConfig"),
    ("cache.streaming",       "from src.cache.streaming import StreamingCache"),
    ("cache.context",         "from src.cache.context import SmartCacheRouter"),
    ("cache.cache_manager",   "from src.cache.cache_manager import CacheManager, CacheManagerConfig, CacheStrategy"),
    ("embedding.base",        "from src.embedding.base import EmbeddingProviderType"),
    ("embedding.service",     "from src.embedding.service import EmbeddingService"),
    ("similarity.base",       "from src.similarity.base import SimilarityMetric"),
    ("similarity.service",    "from src.similarity.service import SimilaritySearchService"),
    ("ml.query_parser",       "from src.ml.query_parser import QueryNormalizer, RuleBasedIntentDetector"),
    ("ml.domain_classifier",  "from src.ml.domain_classifier import KeyWordDomainClassifier"),
    ("ml.adaptive_thresholds","from src.ml.adaptive_thresholds import AdaptiveThresholdManager"),
    ("monitoring.analytics",  "from src.monitoring.analytics import AnalyticsCollector"),
    ("api.config",            "from src.api.config import settings"),
    ("api.auth.jwt",          "from src.api.auth.jwt import create_access_token, get_current_user"),
    ("api.middleware.error",  "from src.api.middleware.error import add_error_handlers"),
    ("api.middleware.security","from src.api.middleware.security import setup_security"),
    ("api.schemas",           "from src.api.schemas import CacheGetResponse, HealthResponse"),
    ("api.routes.health",     "from src.api.routes.health import router as health_router"),
    ("api.routes.admin",      "from src.api.routes.admin import router as admin_router"),
    ("api.routes.tenant",     "from src.api.routes.tenant import router as tenant_router"),
    ("api.routes.search",     "from src.api.routes.search import router as search_router"),
    ("api.routes.analytics",  "from src.api.routes.analytics import router as analytics_router"),
    ("api.routes.cache",      "from src.api.routes.cache import router as cache_router"),
    ("api.main",              "from src.api.main import app"),
]

with open("_diag_results.txt", "w", encoding="utf-8") as f:
    f.write("=== SEMANTIC CACHE DIAGNOSTIC REPORT ===\n\n")
    errors = []
    for name, stmt in checks:
        try:
            exec(stmt, {})
            f.write(f"[OK]  {name}\n")
        except Exception as e:
            tb = traceback.format_exc()
            errors.append((name, stmt, str(e), tb))
            f.write(f"[ERR] {name}: {str(e)[:120]}\n")

    f.write(f"\n\n{'='*60}\n")
    f.write(f"RESULT: {len(checks)-len(errors)}/{len(checks)} passed, {len(errors)} errors\n")
    f.write(f"{'='*60}\n\n")

    for name, stmt, err, tb in errors:
        f.write(f"\n--- ERROR IN: {name} ---\n")
        f.write(f"Statement: {stmt}\n")
        f.write(f"Error: {err}\n")
        f.write(f"Traceback:\n{tb}\n")

print(f"Done. {len(errors)} errors found. See _diag_results.txt")
