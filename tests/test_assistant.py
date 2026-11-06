from fastapi.testclient import TestClient
from app.schemas.assistant import AssistantChatResponse


def test_assistant_chat_customer_query(client: TestClient) -> None:
    """POST /api/v1/assistant/chat responds to customer count inquiries."""
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "How many customers visited today?", "conversationId": "test-c1"},
    )
    assert response.status_code == 200
    data = response.json()
    validated = AssistantChatResponse(**data)
    assert validated.conversationId == "test-c1"
    assert "customer" in validated.answer.lower()
    assert len(validated.suggestedFollowUps) > 0


def test_assistant_chat_shelf_query(client: TestClient) -> None:
    """POST /api/v1/assistant/chat explains shelf monitoring boundaries."""
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Which shelves need restocking?"},
    )
    assert response.status_code == 200
    data = response.json()
    validated = AssistantChatResponse(**data)
    assert "shelf" in validated.answer.lower()
    assert "unavailable" in validated.answer.lower() or "not" in validated.answer.lower()


def test_assistant_chat_general_query(client: TestClient) -> None:
    """POST /api/v1/assistant/chat returns clear capabilities for general queries."""
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "What can you do?"},
    )
    assert response.status_code == 200
    data = response.json()
    validated = AssistantChatResponse(**data)
    assert "retailiq" in validated.answer.lower()
