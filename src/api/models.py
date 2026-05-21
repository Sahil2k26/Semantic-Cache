from pydantic import BaseModel
from typing import List, Optional

class Message(BaseModel):
    """A single turn in the conversation history."""
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    """Stateless chat request with client-side conversation history."""
    query: str
    history: List[Message] = []  # PRIMARY: Full context from client
    context_id: Optional[str] = None  # DEPRECATED: Do NOT use for lookup
    tenant_id: str = "default"
    metadata: Optional[dict] = None
    domain: Optional[str] = "general"  # Keep for compatibility with L1/L2/L3 domain-adaptive thresholds
