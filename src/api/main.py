"""FastAPI application main entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from .config import settings
from .routes import health, cache, search, admin, tenant
from .auth.jwt import add_auth_middleware
from .middleware.error import add_error_handlers
from .middleware.security import setup_security

# Import Phase 1 cache components
from src.cache.cache_manager import CacheManager, CacheManagerConfig, CacheStrategy
from src.cache.base import CacheConfig, EvictionPolicy
from src.cache.redis_config import RedisConfig

# Import Phase 1 embedding and similarity components
from src.embedding.service import EmbeddingService
from src.embedding.base import EmbeddingProviderType
from src.similarity.service import SimilaritySearchService
from src.similarity.base import SimilarityMetric

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Semantic Cache API",
    description="FastAPI REST server for distributed semantic caching system",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GZip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add custom middleware
add_auth_middleware(app)
add_error_handlers(app)
setup_security(app)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(cache.router, prefix="/api/v1/cache", tags=["Cache"])
app.include_router(search.router, prefix="/api/v1", tags=["Search"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(tenant.router, prefix="/api/v1/tenant", tags=["Tenant"])


@app.on_event("startup")
async def startup_event():
    """Handle application startup."""
    logger.info("Starting Semantic Cache API server...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Log level: {settings.LOG_LEVEL}")
    
    # Initialize cache manager
    try:
        # Convert eviction policy string to enum
        eviction_policy = EvictionPolicy(settings.L1_EVICTION_STRATEGY.lower())
        
        l1_config = CacheConfig(
            max_size=settings.L1_MAX_SIZE,
            ttl_seconds=settings.L1_TTL_SECONDS,
            eviction_policy=eviction_policy
        )
        
        l2_config = RedisConfig(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None
        )
        
        # Convert cache strategy string to enum
        cache_strategy = CacheStrategy[settings.CACHE_STRATEGY.upper()]
        
        cache_config = CacheManagerConfig(
            l1_config=l1_config,
            l2_config=l2_config,
            strategy=cache_strategy,
            enable_l1_to_l2_promotion=settings.ENABLE_L1_TO_L2_PROMOTION,
            enable_l2_compression=settings.ENABLE_L2_COMPRESSION
        )
        
        manager = CacheManager(config=cache_config)
        
        if manager.initialize():
            app.state.cache_manager = manager
            manager.start_invalidation_listener()
            logger.info("Cache manager initialized successfully")
        else:
            logger.error("Failed to initialize cache manager")
            app.state.cache_manager = None
            
    except Exception as e:
        logger.error(f"Error initializing cache manager: {e}")
        app.state.cache_manager = None
    
    # Initialize embedding service
    try:
        logger.info("Initializing embedding service...")
        embedding_service = EmbeddingService(
            provider_type=EmbeddingProviderType.SENTENCE_TRANSFORMER,
            model_name="all-MiniLM-L6-v2",
            cache_config={"max_size": 10000, "ttl_seconds": 3600}
        )
        await embedding_service.initialize()
        app.state.embedding_service = embedding_service
        logger.info(f"Embedding service initialized: dimension={embedding_service.provider.embedding_dimension}")
    except Exception as e:
        logger.error(f"Error initializing embedding service: {e}")
        app.state.embedding_service = None
    
    # Initialize similarity search service
    try:
        logger.info("Initializing similarity search service...")
        from src.similarity.service import SimilaritySearchService
        
        similarity_service = SimilaritySearchService(
            metric=SimilarityMetric.COSINE,
            dimension=384,  # all-MiniLM-L6-v2 dimension
            enable_deduplication=True,
            index_config={"m": 16, "ef": 200, "max_m": 48}
        )
        app.state.similarity_service = similarity_service
        logger.info("Similarity search service initialized")
    except Exception as e:
        logger.error(f"Error initializing similarity search service: {e}")
        app.state.similarity_service = None

    # Initialize advanced policies
    try:
        from src.cache.advanced_policies import AdvancedCachingPolicyManager
        app.state.advanced_policies = AdvancedCachingPolicyManager()
        logger.info("Advanced caching policies initialized")
    except Exception as e:
        logger.error(f"Error initializing advanced policies: {e}")
        app.state.advanced_policies = None

    # Initialize performance optimizer
    try:
        from src.cache.performance_opt import PerformanceOptimizer, CompressionFormat
        app.state.performance_optimizer = PerformanceOptimizer(compression_format=CompressionFormat.GZIP)
        logger.info("Performance optimizer initialized")
    except Exception as e:
        logger.error(f"Error initializing performance optimizer: {e}")
        app.state.performance_optimizer = None

    # Initialize tenant manager
    try:
        from src.cache.multi_tenancy import TenantManager
        app.state.tenant_manager = TenantManager()
        logger.info("Tenant manager initialized")
    except Exception as e:
        logger.error(f"Error initializing tenant manager: {e}")
        app.state.tenant_manager = None

    # Initialize ML Components
    try:
        from src.ml.domain_classifier import KeyWordDomainClassifier
        from src.ml.adaptive_thresholds import AdaptiveThresholdManager
        app.state.domain_classifier = KeyWordDomainClassifier()
        app.state.adaptive_thresholds = AdaptiveThresholdManager()
        
        # Start Predictive Cache Warmer
        from src.ml.predictive_warmer import PredictiveCacheWarmer
        warmer = PredictiveCacheWarmer(app.state.cache_manager)
        warmer.start()
        app.state.cache_warmer = warmer
        
        logger.info("Phase 4 ML components initialized")
    except Exception as e:
        logger.error(f"Error initializing ML components: {e}")
        app.state.domain_classifier = None
        app.state.adaptive_thresholds = None



@app.on_event("shutdown")
async def shutdown_event():
    """Handle application shutdown."""
    logger.info("Shutting down Semantic Cache API server...")
    
    # Stop predictive cache warmer
    if hasattr(app.state, 'cache_warmer') and app.state.cache_warmer is not None:
        try:
            app.state.cache_warmer.stop()
            logger.info("Cache warmer stopped")
        except Exception as e:
            logger.error(f"Error stopping cache warmer: {e}")
    
    # Cleanup cache manager
    if hasattr(app.state, 'cache_manager') and app.state.cache_manager is not None:
        try:
            app.state.cache_manager.shutdown()
            logger.info("Cache manager shutdown successfully")
        except Exception as e:
            logger.error(f"Error shutting down cache manager: {e}")
    
    # Cleanup embedding service (minimal cleanup needed)
    if hasattr(app.state, 'embedding_service') and app.state.embedding_service is not None:
        logger.info("Embedding service shutdown")
    
    # Cleanup similarity service (minimal cleanup needed)
    if hasattr(app.state, 'similarity_service') and app.state.similarity_service is not None:
        logger.info("Similarity search service shutdown")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Semantic Cache API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
        workers=settings.API_WORKERS,
        log_level=settings.LOG_LEVEL.lower()
    )
