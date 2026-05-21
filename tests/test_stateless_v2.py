import pytest
from unittest.mock import AsyncMock, MagicMock
from src.ml.local_llm_service import LocalLLMService
from src.cache.context import SmartCacheRouter, QueryType
from src.api.models import Message, ChatRequest

@pytest.mark.asyncio
async def test_local_llm_service_fallback():
    # Test fallback query rewriter when Ollama is offline or unavailable
    service = LocalLLMService(base_url="http://localhost:9999-invalid-port")
    
    # It should gracefully return the original query
    rewritten = await service.rewrite_query(
        query="Who created it?",
        history=[
            Message(role="user", content="What is Python?"),
            Message(role="assistant", content="Python is a popular programming language.")
        ]
    )
    assert rewritten == "Who created it?"

    # It should gracefully return the single query or simple split when offline
    decomposed = await service.decompose_query("Compare Python and Java")
    assert len(decomposed) >= 1
    assert "Compare" in decomposed[0] or "Python" in decomposed[0]

@pytest.mark.asyncio
async def test_smart_cache_router_stateless_single_intent():
    cache_manager = MagicMock()
    cache_manager.get_semantic_async = AsyncMock(return_value=None)
    cache_manager.put_semantic_async = AsyncMock(return_value=True)
    
    local_llm = MagicMock()
    local_llm.rewrite_query = AsyncMock(return_value="Who created Python?")
    local_llm.decompose_query = AsyncMock(return_value=["Who created Python?"])
    
    router = SmartCacheRouter(cache_manager, None, local_llm=local_llm)
    
    # Mock external LLM fallback
    external_llm = MagicMock()
    external_llm.generate_response = AsyncMock(return_value="Guido van Rossum created Python.")
    
    result = await router.handle_chat(
        query="Who created it?",
        history=[Message(role="user", content="What is Python?")],
        llm_service=external_llm
    )
    
    # Assertions
    assert result["hit"] is False
    assert result["response"] == "Guido van Rossum created Python."
    assert result["source"] == "llm_generated"
    assert result["rewritten_query"] == "Who created Python?"
    
    # Verify write-through cache was called for rewritten query
    cache_manager.put_semantic_async.assert_called_with(
        query_text="Who created Python?",
        response="Guido van Rossum created Python.",
        tenant_id="default",
        domain="general",
        metadata={"source": "llm_generated"}
    )

@pytest.mark.asyncio
async def test_smart_cache_router_stateless_multi_intent_all_hit():
    cache_manager = MagicMock()
    
    # Simulate hits for both subqueries
    res_python = MagicMock()
    res_python.entry.response = "Python is dynamic."
    res_python.similarity = 0.95
    res_python.hit_source = "L1"
    
    res_java = MagicMock()
    res_java.entry.response = "Java is static."
    res_java.similarity = 0.96
    res_java.hit_source = "L2"
    
    # Mock get_semantic_async to return hits in order
    cache_manager.get_semantic_async = AsyncMock(side_effect=[res_python, res_java])
    cache_manager.put_semantic_async = AsyncMock(return_value=True)
    
    local_llm = MagicMock()
    local_llm.rewrite_query = AsyncMock(return_value="Compare Python and Java")
    local_llm.decompose_query = AsyncMock(return_value=["What is Python?", "What is Java?"])
    local_llm.synthesize_response = AsyncMock(return_value="Python is dynamic while Java is static.")
    
    router = SmartCacheRouter(cache_manager, None, local_llm=local_llm)
    
    result = await router.handle_chat(
        query="Compare Python and Java",
        history=[]
    )
    
    assert result["hit"] is True
    assert result["response"] == "Python is dynamic while Java is static."
    assert result["source"] == "synthesized_cache"
    
    # Verify write-through stored the synthesized response for the full query
    cache_manager.put_semantic_async.assert_called_with(
        query_text="Compare Python and Java",
        response="Python is dynamic while Java is static.",
        tenant_id="default",
        domain="general",
        metadata={"source": "synthesized_cache"}
    )
