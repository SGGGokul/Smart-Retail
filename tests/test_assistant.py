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


def test_fibonacci_direct_answer(client: TestClient) -> None:
    """Test 1: Fibonacci questions receive direct answers with code and no document fallback."""
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Write a Python Fibonacci program."},
    )
    assert response.status_code == 200
    data = response.json()
    validated = AssistantChatResponse(**data)
    answer = validated.answer
    assert "fibonacci" in answer.lower()
    assert "def fibonacci" in answer or "```python" in answer or "```" in answer
    assert "store operational documents do not contain" not in answer.lower()


def test_programming_questions_no_document_fallback(client: TestClient) -> None:
    """Test 2: Programming and algorithm questions do not trigger document-not-found messages."""
    # Test binary search
    resp_bs = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Explain binary search."},
    )
    assert resp_bs.status_code == 200
    data_bs = resp_bs.json()
    ans_bs = data_bs["answer"]
    assert "binary search" in ans_bs.lower()
    assert "store operational documents do not contain" not in ans_bs.lower()

    # Test OOP
    resp_oop = client.post(
        "/api/v1/assistant/chat",
        json={"message": "What is object-oriented programming?"},
    )
    assert resp_oop.status_code == 200
    data_oop = resp_oop.json()
    ans_oop = data_oop["answer"]
    assert "object-oriented" in ans_oop.lower() or "encapsulation" in ans_oop.lower() or "polymorphism" in ans_oop.lower()
    assert "store operational documents do not contain" not in ans_oop.lower()


def test_store_policy_uses_document_retrieval(client: TestClient) -> None:
    """Test 3: Store policy questions use document retrieval and include valid citations."""
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "What is the store return policy?"},
    )
    assert response.status_code == 200
    data = response.json()
    validated = AssistantChatResponse(**data)
    answer = validated.answer.lower()
    assert "return" in answer or "30 days" in answer
    # Grounded citations must be preserved
    assert "store_operating_procedures.txt" in validated.answer or "Source:" in validated.answer


def test_customer_count_uses_actual_analytics_data(client: TestClient) -> None:
    """Test 4: Customer-count questions use actual analytics data without fabricating counts."""
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "How many customers visited today?"},
    )
    assert response.status_code == 200
    data = response.json()
    validated = AssistantChatResponse(**data)
    answer = validated.answer.lower()
    assert "customer" in answer or "footfall" in answer
    # Uses actual data (0 if newly initialized) and never invents arbitrary counts
    assert "store footfall" in answer or "detected today" in answer or "0 customer" in answer


def test_missing_store_data_never_fabricates_numbers(client: TestClient) -> None:
    """Test 5: Missing store data or unknown customer IDs explicitly report missing history without fabrication."""
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Show me the visit history for CUST-999999."},
    )
    assert response.status_code == 200
    data = response.json()
    validated = AssistantChatResponse(**data)
    answer = validated.answer.lower()
    assert "cust-999999" in answer
    assert "no tracking history found" in answer


def test_mixed_questions_combine_both_sources(client: TestClient) -> None:
    """Test 6: Mixed questions correctly combine store information and general knowledge."""
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "What is the store return policy and write a Python Fibonacci program?"},
    )
    assert response.status_code == 200
    data = response.json()
    validated = AssistantChatResponse(**data)
    answer = validated.answer.lower()
    # Must answer store return policy
    assert "return" in answer
    # Must answer Fibonacci programming query
    assert "fibonacci" in answer
    # Must NOT say store operational documents do not contain information
    assert "store operational documents do not contain" not in answer

