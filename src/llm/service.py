import json
import logging
from typing import Optional, AsyncGenerator
import httpx

from src.core.config import LLMConfig
from src.utils.logging import get_logger

logger = get_logger(__name__)

class LLMService:
    """Service for interacting with language models."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.provider = config.provider.lower()
        self.api_key = config.api_key
        self.model = config.model or "gemini-pro"
        
        if not self.api_key:
            logger.warning(f"No API key provided for LLM service (provider: {self.provider}). LLM features may fail.")

    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Generate a response using the configured LLM provider."""
        if not self.api_key:
            return f"Error: No API key configured for {self.provider}"
            
        try:
            if self.provider == "gemini":
                return await self._call_gemini(prompt, system_prompt)
            elif self.provider == "openai":
                return await self._call_openai(prompt, system_prompt)
            else:
                logger.error(f"Unsupported LLM provider: {self.provider}")
                return None
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            return None

    async def generate_stream(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Generate a streaming response using the configured LLM provider."""
        if not self.api_key:
            yield f"Error: No API key configured for {self.provider}"
            return
            
        try:
            if self.provider == "gemini":
                async for chunk in self._stream_gemini(prompt, system_prompt):
                    yield chunk
            elif self.provider == "openai":
                async for chunk in self._stream_openai(prompt, system_prompt):
                    yield chunk
            else:
                logger.error(f"Unsupported LLM provider for streaming: {self.provider}")
                yield f"Error: Unsupported provider {self.provider}"
        except Exception as e:
            logger.error(f"Error streaming LLM response: {e}")
            yield f"Error: Generation failed due to internal error."

    async def _call_gemini(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Call Gemini REST API for standard generation."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        parts = []
        if system_prompt:
            parts.append({"text": f"System: {system_prompt}\n\n"})
        parts.append({"text": prompt})
        
        payload = {
            "contents": [
                {
                    "parts": parts
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as e:
                logger.error(f"Unexpected response format from Gemini: {data}")
                return "Error: Could not parse response from Gemini."

    async def _stream_gemini(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Call Gemini REST API for streaming generation."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
        
        parts = []
        if system_prompt:
            parts.append({"text": f"System: {system_prompt}\n\n"})
        parts.append({"text": prompt})
        
        payload = {
            "contents": [
                {
                    "parts": parts
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, json=payload, timeout=60.0) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(data_str)
                            if "candidates" in data and len(data["candidates"]) > 0:
                                candidate = data["candidates"][0]
                                if "content" in candidate and "parts" in candidate["content"]:
                                    part = candidate["content"]["parts"][0]
                                    if "text" in part:
                                        yield part["text"]
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse SSE data: {data_str}")
                        except Exception as e:
                            logger.error(f"Error processing stream chunk: {e}")

    async def _call_openai(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Placeholder for OpenAI standard generation."""
        # This is a stub for future modularity
        logger.warning("OpenAI integration not yet implemented")
        return "OpenAI integration not yet implemented"
        
    async def _stream_openai(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Placeholder for OpenAI streaming generation."""
        logger.warning("OpenAI streaming integration not yet implemented")
        yield "OpenAI streaming integration not yet implemented"
