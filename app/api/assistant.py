from fastapi import APIRouter

from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from app.services.assistant_service import get_assistant_service

router = APIRouter()


@router.post(
    "/chat",
    response_model=AssistantChatResponse,
    summary="RetailIQ AI Assistant chat",
)
async def chat_assistant(payload: AssistantChatRequest) -> AssistantChatResponse:
    """Sends user retail queries to the assistant service."""
    assistant_service = get_assistant_service()
    return assistant_service.handle_chat(payload)
