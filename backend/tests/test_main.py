import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

MOCK_VALID_RESPONSE = {
    "score": 85,
    "verdict": "Malicious",
    "reasoning": "The sender domain does not match the display name. The email uses urgent language to pressure the recipient. A reply-to address pointing to a different domain is a strong phishing signal.",
    "flags": [
        "Sender domain mismatch",
        "Urgency language",
        "Reply-to domain mismatch",
    ],
}


def _make_mock_response(text: str) -> MagicMock:
    mock_response = MagicMock()
    mock_response.text = text
    return mock_response


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_missing_fields_returns_422() -> None:
    response = client.post("/analyze", json={})
    assert response.status_code == 422


def test_analyze_body_truncated() -> None:
    long_body = "A" * 10_000
    payload = {
        "subject": "Test",
        "sender": "test@example.com",
        "body": long_body,
    }
    mock_response = _make_mock_response(json.dumps(MOCK_VALID_RESPONSE))
    with patch("main.client") as mock_client:
        mock_client.models.generate_content.return_value = mock_response
        response = client.post("/analyze", json=payload)

    assert response.status_code == 200
    prompt_arg = mock_client.models.generate_content.call_args[1]["contents"]
    # Extract just the body section from the prompt and verify it's ≤ 3000 chars
    body_start = prompt_arg.index("Body: ") + len("Body: ")
    body_end = prompt_arg.index("\n\nCheck:", body_start)
    body_in_prompt = prompt_arg[body_start:body_end]
    assert len(body_in_prompt) <= 3000


def test_analyze_returns_expected_shape() -> None:
    payload = {
        "subject": "Urgent: Verify your account now",
        "sender": "security@paypa1.com",
        "reply_to": "harvester@randomdomain.ru",
        "body": "Click here immediately to restore access.",
        "date": "2026-05-15",
    }
    mock_response = _make_mock_response(json.dumps(MOCK_VALID_RESPONSE))
    with patch("main.client") as mock_client:
        mock_client.models.generate_content.return_value = mock_response
        response = client.post("/analyze", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["score"], int)
    assert data["verdict"] in ("Safe", "Suspicious", "Malicious")
    assert isinstance(data["reasoning"], str)
    assert isinstance(data["flags"], list)


def test_analyze_invalid_json_from_gemini() -> None:
    payload = {
        "subject": "Hello",
        "sender": "someone@example.com",
        "body": "Just a friendly message.",
    }
    mock_response = _make_mock_response("not valid json at all }{")
    with patch("main.client") as mock_client:
        mock_client.models.generate_content.return_value = mock_response
        response = client.post("/analyze", json=payload)

    assert response.status_code == 502
    data = response.json()
    assert "error" in data
    # Must not expose internal stack traces
    assert "Traceback" not in data["error"]
    assert "JSONDecodeError" not in data["error"]
