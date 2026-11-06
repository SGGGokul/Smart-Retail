from typing import List, Optional
from pydantic import BaseModel, Field


class AssistantChatRequest(BaseModel):
    """User retail query sent to AI assistant."""
    message: str
    conversationId: Optional[str] = None


class AssistantChatResponse(BaseModel):
    """AI assistant reply with conversational context."""
    answer: str
    conversationId: str
    suggestedFollowUps: Optional[List[str]] = Field(default_factory=list)
