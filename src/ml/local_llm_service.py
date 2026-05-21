import json
import logging
from typing import List, Optional, Dict, Any, Union
import httpx

logger = logging.getLogger(__name__)

class LocalLLMService:
    """Service for processing text via local Qwen2.5-1.5B via Ollama.
    Uses stateless client-side history and supports robust direct REST fallback 
    if the 'ollama' Python SDK is not installed or encounters issues.
    """
    def __init__(self, base_url: str = "http://localhost:11434", model_name: str = "qwen2.5:1.5b"):
        self.base_url = base_url
        self.model_name = model_name
        
        # Try to import ollama SDK
        try:
            import ollama
            self._client = ollama
            self._has_sdk = True
            logger.info("Ollama Python SDK successfully loaded.")
        except ImportError:
            self._client = None
            self._has_sdk = False
            logger.info("Ollama Python SDK not found. Using direct HTTP REST fallback.")

    async def _generate(self, prompt: str, system: Optional[str] = None) -> str:
        """Helper to invoke Ollama generation. Prioritizes fully async direct REST calls for FastAPI."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0  # Greedy decoding for high precision rewriting/decomposition
            }
        }
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "").strip()
        except Exception as e:
            logger.error(f"Failed to query local Ollama service: {e}")
            raise e

    async def rewrite_query(self, query: str, history: List[Any]) -> str:
        """Rewrite a contextual query into a standalone query using conversation history."""
        if not history:
            return query
            
        # Format the conversation history
        history_lines = []
        for msg in history:
            # Handle both pydantic models and dictionaries
            role = "User" if getattr(msg, "role", "").lower() == "user" or (isinstance(msg, dict) and msg.get("role", "").lower() == "user") else "Assistant"
            content = getattr(msg, "content", "") if hasattr(msg, "content") else (msg.get("content", "") if isinstance(msg, dict) else str(msg))
            history_lines.append(f"{role}: {content}")
        
        history_text = "\n".join(history_lines)
        
        system_prompt = (
            "You are an expert search query rewriter. "
            "Your task is to rewrite the latest user query to be a standalone, clear, and search-friendly query "
            "that contains all necessary context (e.g. replacing pronouns like 'it', 'he', 'that' with their referents from the conversation history). "
            "Do NOT answer the query. Do NOT explain your answer. Output ONLY the rewritten standalone query."
        )
        
        prompt = (
            f"Conversation History:\n{history_text}\n\n"
            f"Latest User Query: {query}\n\n"
            f"Rewritten Standalone Query:"
        )
        
        try:
            rewritten = await self._generate(prompt, system=system_prompt)
            # Basic cleaning in case model adds prefixes
            if rewritten.lower().startswith("rewritten standalone query:"):
                rewritten = rewritten[len("rewritten standalone query:"):].strip()
            # Clean outer quotes if any
            if (rewritten.startswith('"') and rewritten.endswith('"')) or (rewritten.startswith("'") and rewritten.endswith("'")):
                rewritten = rewritten[1:-1].strip()
            return rewritten if rewritten else query
        except Exception as e:
            logger.warning(f"Error during query rewriting: {e}. Using original query.")
            return query

    async def decompose_query(self, query: str) -> List[str]:
        """Decompose a complex multi-intent query into simpler, independent sub-queries."""
        system_prompt = (
            "You are a query decomposition assistant. Your task is to break down a complex multi-intent query "
            "into a JSON list of simpler, independent, standalone sub-queries. "
            "If the query has only a single intent, return a JSON list containing just the original query.\n"
            "Requirements:\n"
            "1. Output ONLY a valid JSON list of strings.\n"
            "2. Do NOT include any explanations, markdown code blocks (e.g. ```json), or other characters outside the JSON."
        )
        
        prompt = f"Query: {query}\nJSON List of sub-queries:"
        
        try:
            raw_response = await self._generate(prompt, system=system_prompt)
            
            # Clean response for JSON parsing
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            # Try to parse JSON
            sub_queries = json.loads(cleaned)
            if isinstance(sub_queries, list):
                # Ensure all items are strings and non-empty
                result = [str(item).strip() for item in sub_queries if item]
                return result if result else [query]
            return [query]
        except Exception as e:
            logger.warning(f"Error during query decomposition: {e}. Falling back to single query.")
            # Simple rule-based regex fallback as graceful degradation
            if " and " in query or " vs " in query or " compare " in query.lower():
                parts = [p.strip() for p in query.replace("?", "").split(" and ") if p.strip()]
                if len(parts) > 1:
                    return parts
            return [query]

    async def synthesize_response(self, original_query: str, sub_answers: Union[List[str], List[Dict[str, Any]]]) -> str:
        """Synthesize answers from sub-queries into a cohesive response answering the original query."""
        # Convert sub_answers to a structured string
        sub_answers_lines = []
        for i, item in enumerate(sub_answers):
            if isinstance(item, dict):
                q = item.get("query", f"Part {i+1}")
                a = item.get("response", "No answer found.")
                sub_answers_lines.append(f"Sub-Query: {q}\nAnswer: {a}")
            else:
                sub_answers_lines.append(f"Answer Part {i+1}: {item}")
                
        sub_answers_text = "\n\n".join(sub_answers_lines)
        
        system_prompt = (
            "You are an answer synthesis assistant. Your task is to combine the provided answers to sub-queries "
            "into a single, cohesive, comprehensive, and natural-sounding response that directly and fully answers the original user query. "
            "Do NOT mention 'sub-queries' or 'synthesized response' in your output. Just output the final cohesive response."
        )
        
        prompt = (
            f"Original Query: {original_query}\n\n"
            f"Sub-Answers:\n{sub_answers_text}\n\n"
            f"Final Cohesive Response:"
        )
        
        try:
            synthesized = await self._generate(prompt, system=system_prompt)
            return synthesized
        except Exception as e:
            logger.warning(f"Error during response synthesis: {e}. Concatenating sub-answers.")
            # Fallback concat
            fallback_parts = []
            for item in sub_answers:
                if isinstance(item, dict):
                    fallback_parts.append(f"- {item.get('response', '')}")
                else:
                    fallback_parts.append(f"- {item}")
            return "\n".join(fallback_parts)
