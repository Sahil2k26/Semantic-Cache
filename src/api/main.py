"""FastAPI application main entry point with semantic cache integration."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
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

# Import unified index manager (Gap #2 fix)
from src.cache.index_manager import UnifiedIndexManager, IndexConfig

# Import Phase 1 embedding and similarity components
from src.embedding.service import EmbeddingService
from src.embedding.base import EmbeddingProviderType
from src.similarity.service import SimilaritySearchService
from src.similarity.base import SimilarityMetric

# Import database initialization (Fix for Gap: Database not initialized at startup)
from src.core.database import init_database
from src.core.config import SemanticCacheConfig, DatabaseConfig, LLMConfig

# Import LLM service
from src.llm.service import LLMService

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "font-src 'self' data: https://cdn.jsdelivr.net https://fonts.gstatic.com; "
    "connect-src 'self'"
)

# Create FastAPI application
app = FastAPI(
    title="Semantic Cache API",
    description="FastAPI REST server for distributed semantic caching system",
    version="2.0.0",
    docs_url=None,
    redoc_url=None,
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


@app.get("/docs", include_in_schema=False)
async def swagger_ui_html():
    """Serve Swagger UI with a CSP compatible with its assets."""
    response = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
    )
    response.headers["Content-Security-Policy"] = DOCS_CSP
    return response


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    """Serve Swagger UI OAuth2 redirect helper with the docs CSP."""
    response = get_swagger_ui_oauth2_redirect_html()
    response.headers["Content-Security-Policy"] = DOCS_CSP
    return response


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    """Serve ReDoc with a CSP compatible with its assets."""
    response = get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
    )
    response.headers["Content-Security-Policy"] = DOCS_CSP
    return response


@app.on_event("startup")
async def startup_event():
    """Handle application startup with integrated semantic caching."""
    logger.info("Starting Semantic Cache API server...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Log level: {settings.LOG_LEVEL}")
    
    # Step 0: Initialize Database
    # ========================================================================
    try:
        logger.info("Initializing database...")
        # Create a config object for the database manager using API settings
        db_config = DatabaseConfig(
            url=settings.DATABASE_URL,
            pool_size=settings.CONNECTION_POOL_SIZE,
            max_overflow=settings.CONNECTION_POOL_SIZE // 2
        )
        core_config = SemanticCacheConfig(database=db_config)
        db_manager = init_database(core_config)
        
        # Create tables if they don't exist
        db_manager.create_all_tables()
        logger.info("Database initialized and tables verified")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

    # ========================================================================
    # Step 1: Initialize Unified Index Manager (Gap #2 Fix)
    # This creates a single HNSW index shared by all components
    # ========================================================================
    try:
        logger.info("Initializing unified index manager...")
        index_config = IndexConfig(
            dimension=384,  # all-MiniLM-L6-v2 dimension
            m=16,
            ef=200,
            metric=SimilarityMetric.COSINE
        )
        index_manager = UnifiedIndexManager.get_instance(index_config)
        app.state.index_manager = index_manager
        logger.info(f"Unified index manager initialized: dim={index_config.dimension}")
    except Exception as e:
        logger.error(f"Error initializing index manager: {e}")
        app.state.index_manager = None
    
    # ========================================================================
    # Step 2: Initialize Embedding Service
    # This generates embeddings for semantic search
    # ========================================================================
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
    
    # ========================================================================
    # Step 3: Initialize Domain Classifier & Threshold Manager (Gap #6 Fix)
    # These enable domain-adaptive similarity thresholds
    # ========================================================================
    domain_classifier = None
    threshold_manager = None
    try:
        from src.ml.domain_classifier import KeyWordDomainClassifier
        from src.ml.adaptive_thresholds import AdaptiveThresholdManager
        domain_classifier = KeyWordDomainClassifier()
        threshold_manager = AdaptiveThresholdManager()
        app.state.domain_classifier = domain_classifier
        app.state.adaptive_thresholds = threshold_manager
        logger.info("Domain classifier and threshold manager initialized")
    except Exception as e:
        logger.warning(f"ML components not available: {e}")
        app.state.domain_classifier = None
        app.state.adaptive_thresholds = None
    
    # ========================================================================
    # Step 4: Initialize Cache Manager with Semantic Integration (Gap #1, #3, #7 Fix)
    # Wire embedding service, index manager, and domain classifier
    # ========================================================================
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
            enable_l2_compression=settings.ENABLE_L2_COMPRESSION,
            # Semantic search settings
            enable_semantic_search=True,
            default_similarity_threshold=0.85,
            embedding_dimension=384
        )
        
        manager = CacheManager(config=cache_config)
        
        if manager.initialize():
            # Wire semantic components (Gap #1, #3, #7 Fix)
            if app.state.index_manager:
                manager.set_index_manager(app.state.index_manager)
                logger.info("Cache manager connected to unified index")
            
            if app.state.embedding_service:
                manager.set_embedding_service(app.state.embedding_service)
                logger.info("Cache manager connected to embedding service")
            
            if domain_classifier:
                manager.set_domain_classifier(domain_classifier)
                logger.info("Cache manager connected to domain classifier")
            
            if threshold_manager:
                manager.set_threshold_manager(threshold_manager)
                logger.info("Cache manager connected to threshold manager")
            
            app.state.cache_manager = manager
            manager.start_invalidation_listener()
            logger.info("Cache manager initialized with semantic search integration")
        else:
            logger.error("Failed to initialize cache manager")
            app.state.cache_manager = None
            
    except Exception as e:
        logger.error(f"Error initializing cache manager: {e}")
        app.state.cache_manager = None
    
    # ========================================================================
    # Step 5: Initialize Similarity Search Service (Facade Pattern)
    # Now delegates ALL indexing to UnifiedIndexManager
    # ========================================================================
    try:
        logger.info("Initializing similarity search service...")
        similarity_service = SimilaritySearchService(
            metric=SimilarityMetric.COSINE,
            dimension=384,  # all-MiniLM-L6-v2 dimension
            enable_deduplication=True,
            index_manager=app.state.index_manager,  # Pass index manager directly
        )
        
        app.state.similarity_service = similarity_service
        logger.info(f"Similarity search service initialized (facade pattern, index_manager={'connected' if app.state.index_manager else 'not set'})")
    except Exception as e:
        logger.error(f"Error initializing similarity search service: {e}")
        app.state.similarity_service = None

    # ========================================================================
    # Step 6: Initialize Advanced Policies & Performance Optimizer
    # ========================================================================
    try:
        from src.cache.advanced_policies import AdvancedCachingPolicyManager
        app.state.advanced_policies = AdvancedCachingPolicyManager()
        logger.info("Advanced caching policies initialized")
    except Exception as e:
        logger.error(f"Error initializing advanced policies: {e}")
        app.state.advanced_policies = None

    try:
        from src.cache.performance_opt import PerformanceOptimizer, CompressionFormat
        app.state.performance_optimizer = PerformanceOptimizer(compression_format=CompressionFormat.GZIP)
        logger.info("Performance optimizer initialized")
    except Exception as e:
        logger.error(f"Error initializing performance optimizer: {e}")
        app.state.performance_optimizer = None

    # ========================================================================
    # Step 7: Initialize Tenant Manager
    # ========================================================================
    try:
        from src.core.tenant_manager import TenantManager
        app.state.tenant_manager = TenantManager()
        logger.info("Tenant manager initialized")
    except Exception as e:
        logger.error(f"Error initializing tenant manager: {e}")
        app.state.tenant_manager = None

    # ========================================================================
    # Step 8: Start Predictive Cache Warmer
    # ========================================================================
    try:
        from src.ml.predictive_warmer import PredictiveCacheWarmer
        warmer = PredictiveCacheWarmer(app.state.cache_manager)
        warmer.start()
        app.state.cache_warmer = warmer
        logger.info("Predictive cache warmer started")
    except Exception as e:
        logger.error(f"Error initializing cache warmer: {e}")
        app.state.cache_warmer = None
        
    # ========================================================================
    # Step 9: Initialize LLM Service
    # ========================================================================
    try:
        logger.info("Initializing LLM service...")
        llm_config = LLMConfig(
            provider=settings.LLM_PROVIDER,
            api_key=settings.LLM_API_KEY or None,
            model=settings.LLM_MODEL,
        )
        llm_service = LLMService(llm_config)
        app.state.llm_service = llm_service
        logger.info(f"LLM service initialized (provider: {settings.LLM_PROVIDER}, model: {settings.LLM_MODEL})")
    except Exception as e:
        logger.error(f"Error initializing LLM service: {e}")
        app.state.llm_service = None
    
    logger.info("=" * 60)
    logger.info("Semantic Cache API startup complete!")
    logger.info(f"  - Unified Index:     {'✓' if app.state.index_manager else '✗'}")
    logger.info(f"  - Embedding Service: {'✓' if app.state.embedding_service else '✗'}")
    logger.info(f"  - Cache Manager:     {'✓' if app.state.cache_manager else '✗'}")
    logger.info(f"  - Domain Classifier: {'✓' if app.state.domain_classifier else '✗'}")
    logger.info(f"  - Similarity Search: {'✓' if app.state.similarity_service else '✗'}")
    logger.info(f"  - LLM Service:       {'✓' if app.state.llm_service else '✗'}")
    logger.info("=" * 60)



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
    
    # Cleanup unified index manager
    if hasattr(app.state, 'index_manager') and app.state.index_manager is not None:
        try:
            # Reset the singleton for clean restart
            UnifiedIndexManager._instance = None
            logger.info("Index manager shutdown")
        except Exception as e:
            logger.error(f"Error shutting down index manager: {e}")
    
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
