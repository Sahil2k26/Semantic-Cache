import logging
import asyncio
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from src.ml.local_llm_service import LocalLLMService

logger = logging.getLogger(__name__)

class QueryType(Enum):
    STATELESS = "stateless"       # Query can stand alone
    CONTEXTUAL = "contextual"     # Query refers to past conversation turns
    AMBIGUOUS = "ambiguous"       # Could go either way

class SmartCacheRouter:
    """
    Stateless, context-aware router that detects context needs,
    rewrites queries using client-provided history via a local LLM,
    decomposes multi-intent queries, and routes lookups to L1/L2/L3.
    
    CRITICAL: Avoids server-side session history in Redis. Redis is solely
    used for caching query-response pairs.
    """
    def __init__(self, cache_manager, embedding_service, local_llm=None):
        self.cache_manager = cache_manager
        self.embedding_service = embedding_service
        self.local_llm = local_llm or LocalLLMService()
        
        self.metrics = {
            "stateless_hits": 0,
            "contextual_hits": 0,
            "routing_decisions": []
        }

    async def handle_chat(
        self,
        query: str,
        history: List[Any],
        context_id: Optional[str] = None,
        tenant_id: str = "default",
        domain: str = "general",
        threshold: Optional[float] = None,
        metadata: Optional[dict] = None,
        llm_service: Optional[Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Handles context-aware and multi-intent queries statelessly.
        
        1. Rewrites query using provided history from client.
        2. Decomposes query into independent sub-queries.
        3. Parallel cache lookups across L1/L2/L3.
        4. Synthesizes response on multi-intent hits, or falls back to LLM on misses.
        """
        # Step 1: Rewrite contextual query to standalone
        rewritten_query = await self.local_llm.rewrite_query(query, history)
        logger.info(f"Original query: '{query}' -> Standalone query: '{rewritten_query}'")
        
        # Step 2: Decompose query
        sub_queries = await self.local_llm.decompose_query(rewritten_query)
        logger.info(f"Decomposed sub-queries: {sub_queries}")
        
        # Step 3: Parallel Cache Search
        tasks = [
            self.cache_manager.get_semantic_async(
                query_text=sq,
                tenant_id=tenant_id,
                domain=domain,
                threshold=threshold,
                **kwargs
            ) for sq in sub_queries
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Analyze hits
        sub_results = []
        all_hit = True
        
        for sq, res in zip(sub_queries, results):
            hit = res is not None and res.entry is not None
            sub_results.append({
                "query": sq,
                "hit": hit,
                "response": res.entry.response if hit else None,
                "similarity": res.similarity if hit else 0.0,
                "source": res.hit_source.lower() if (hit and hasattr(res, "hit_source")) else "none"
            })
            if not hit:
                all_hit = False

        # Step 4: Execution & Synthesis Logic
        if len(sub_queries) == 1:
            # Single intent
            if all_hit:
                logger.info("Single intent semantic cache HIT.")
                self.metrics["stateless_hits"] += 1
                return {
                    "response": sub_results[0]["response"],
                    "hit": True,
                    "source": sub_results[0]["source"],
                    "rewritten_query": rewritten_query,
                    "sub_queries": sub_queries,
                    "sub_query_results": sub_results
                }
            else:
                logger.info("Single intent semantic cache MISS. Querying external LLM.")
                response_text = "LLM service not configured."
                if llm_service:
                    response_text = await llm_service.generate_response(rewritten_query)
                    if not response_text or response_text.startswith("Error:"):
                        response_text = f"Failed to generate response for: {rewritten_query}"
                
                # Write-through to L1/L2/L3 cache
                if response_text and not response_text.startswith("Failed to generate"):
                    await self.cache_manager.put_semantic_async(
                        query_text=rewritten_query,
                        response=response_text,
                        tenant_id=tenant_id,
                        domain=domain,
                        metadata=metadata or {"source": "llm_generated"}
                    )
                
                return {
                    "response": response_text,
                    "hit": False,
                    "source": "llm_generated",
                    "rewritten_query": rewritten_query,
                    "sub_queries": sub_queries,
                    "sub_query_results": sub_results
                }
        else:
            # Multi-intent query
            if all_hit:
                logger.info("Multi-intent cache HIT for ALL sub-queries. Synthesizing response.")
                self.metrics["contextual_hits"] += 1
                
                # Extract answers
                sub_answers = [
                    {"query": item["query"], "response": item["response"]}
                    for item in sub_results
                ]
                
                synthesized = await self.local_llm.synthesize_response(query, sub_answers)
                
                # Also store the synthesized response for the full query
                await self.cache_manager.put_semantic_async(
                    query_text=query,
                    response=synthesized,
                    tenant_id=tenant_id,
                    domain=domain,
                    metadata={"source": "synthesized_cache"}
                )
                
                return {
                    "response": synthesized,
                    "hit": True,
                    "source": "synthesized_cache",
                    "rewritten_query": rewritten_query,
                    "sub_queries": sub_queries,
                    "sub_query_results": sub_results
                }
            else:
                logger.info("Multi-intent cache MISS for one or more sub-queries. Querying external LLM.")
                response_text = "LLM service not configured."
                if llm_service:
                    response_text = await llm_service.generate_response(rewritten_query)
                    if not response_text or response_text.startswith("Error:"):
                        response_text = f"Failed to generate response for: {rewritten_query}"
                
                # Write-through full query to L1/L2/L3
                if response_text and not response_text.startswith("Failed to generate"):
                    await self.cache_manager.put_semantic_async(
                        query_text=rewritten_query,
                        response=response_text,
                        tenant_id=tenant_id,
                        domain=domain,
                        metadata=metadata or {"source": "llm_generated"}
                    )
                    
                    # Also write through any individual successful sub-queries
                    for item in sub_results:
                        if item["hit"] and item["response"]:
                            await self.cache_manager.put_semantic_async(
                                query_text=item["query"],
                                response=item["response"],
                                tenant_id=tenant_id,
                                domain=domain,
                                metadata={"source": "sub_query_cache"}
                            )
                
                return {
                    "response": response_text,
                    "hit": False,
                    "source": "llm_generated",
                    "rewritten_query": rewritten_query,
                    "sub_queries": sub_queries,
                    "sub_query_results": sub_results
                }

    async def get(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
        tenant_id: str = "default",
        domain: str = "general",
        threshold: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Backward compatible get method. Bypasses old Redis state storage and uses handle_chat format.
        """
        history = conversation_history or []
        rewritten_query = await self.local_llm.rewrite_query(query, history)
        sub_queries = await self.local_llm.decompose_query(rewritten_query)
        
        tasks = [
            self.cache_manager.get_semantic_async(
                query_text=sq,
                tenant_id=tenant_id,
                domain=domain,
                threshold=threshold,
                **kwargs
            ) for sq in sub_queries
        ]
        
        results = await asyncio.gather(*tasks)
        
        sub_results = []
        all_hit = True
        for sq, res in zip(sub_queries, results):
            hit = res is not None and res.entry is not None
            sub_results.append({
                "query": sq,
                "hit": hit,
                "response": res.entry.response if hit else None,
                "similarity": res.similarity if hit else 0.0,
                "source": res.hit_source.lower() if (hit and hasattr(res, "hit_source")) else "none"
            })
            if not hit:
                all_hit = False
                
        if all_hit:
            if len(sub_queries) == 1:
                return {
                    "hit": True,
                    "response": sub_results[0]["response"],
                    "routed_to": "semantic_cache",
                    "query_type": "stateless",
                    "rewritten_query": rewritten_query
                }
            else:
                # Multi-intent hit -> synthesize
                sub_answers = [
                    {"query": item["query"], "response": item["response"]}
                    for item in sub_results
                ]
                synthesized = await self.local_llm.synthesize_response(query, sub_answers)
                return {
                    "hit": True,
                    "response": synthesized,
                    "routed_to": "synthesized_cache",
                    "query_type": "contextual",
                    "rewritten_query": rewritten_query
                }
                
        return {
            "hit": False,
            "response": None,
            "routed_to": "semantic_cache",
            "query_type": "stateless"
        }

    async def set(
        self,
        query: str,
        response: str,
        conversation_id: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
        tenant_id: str = "default",
        domain: str = "general",
        **kwargs
    ):
        """
        Backward compatible set method. Bypasses Redis history save, stores pair in L1/L2/L3 cache.
        """
        history = conversation_history or []
        rewritten_query = await self.local_llm.rewrite_query(query, history)
        
        await self.cache_manager.put_semantic_async(
            query_text=rewritten_query,
            response=response,
            tenant_id=tenant_id,
            domain=domain,
            metadata={"source": "api_set"}
        )
        
        if rewritten_query != query:
            await self.cache_manager.put_semantic_async(
                query_text=query,
                response=response,
                tenant_id=tenant_id,
                domain=domain,
                metadata={"source": "api_set_contextual"}
            )

class ContextAwareCache:
    """
    DEPRECATED: Backward compatible stub for ContextAwareCache.
    Now completely stateless and performs no Redis session operations.
    """
    def __init__(self, base_cache_manager, embedding_service):
        self.cache = base_cache_manager
        self.embedder = embedding_service

    async def get(self, query: str, conversation_id: str, conversation_history: List[Dict]) -> Dict:
        return {"hit": False}

    async def set(self, query: str, response: str, conversation_id: str, conversation_history: List[Dict]):
        pass

