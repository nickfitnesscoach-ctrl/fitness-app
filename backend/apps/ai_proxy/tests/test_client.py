"""
test_client.py — unit tests for AIProxyClient.

Проверяем:
- 400 + error_code → AIProxyResult(ok=False) with Error Contract
- 400 без error_code → AIProxyValidationError exception
- 2xx + payload → AIProxyResult(ok=True)
- 401/403 → AIProxyAuthenticationError
- 5xx → AIProxyServerError
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from apps.ai_proxy.client import AIProxyClient, AIProxyConfig, AIProxyResult
from apps.ai_proxy.exceptions import (
    AIProxyAuthenticationError,
    AIProxyServerError,
    AIProxyValidationError,
)


@pytest.fixture
def client():
    """Create test client with mock config."""
    config = AIProxyConfig(url="http://test-proxy", secret="test-secret")
    return AIProxyClient(config=config)


@pytest.fixture
def mock_response():
    """Factory for creating mock HTTP responses."""
    def _make_response(status_code: int, json_data: dict | None = None):
        resp = Mock()
        resp.status_code = status_code
        resp.text = ""
        if json_data is not None:
            import json as json_mod
            resp.text = json_mod.dumps(json_data)
        return resp
    return _make_response


class TestAIProxyClient:
    """Tests for AIProxyClient.recognize_food()."""

    def test_400_with_error_code_returns_structured_error(self, client, mock_response):
        """
        Test: AI Proxy возвращает 400 + Error Contract (UNSUPPORTED_CONTENT)
        Expected: AIProxyResult(ok=False) с payload Error Contract
        """
        error_contract = {
            "error_code": "UNSUPPORTED_CONTENT",
            "user_title": "Похоже, на фото не еда",
            "user_message": "Сфотографируйте блюдо крупнее при хорошем освещении.",
            "user_actions": ["retake"],
            "allow_retry": False,
            "trace_id": "test-trace-id",
        }

        with patch.object(client._session, "post") as mock_post:
            mock_post.return_value = mock_response(400, error_contract)

            result = client.recognize_food(
                image_bytes=b"fake-image",
                content_type="image/jpeg",
                request_id="test-req",
            )

            # Должен вернуть AIProxyResult(ok=False), а НЕ exception
            assert isinstance(result, AIProxyResult)
            assert result.ok is False
            assert result.status_code == 400
            assert result.payload == error_contract
            assert result.payload["error_code"] == "UNSUPPORTED_CONTENT"

    def test_400_without_error_code_raises_validation_error(self, client, mock_response):
        """
        Test: AI Proxy возвращает 400 БЕЗ error_code (FastAPI validation error)
        Expected: AIProxyValidationError exception
        """
        validation_error = {
            "detail": [
                {"loc": ["body", "image"], "msg": "field required", "type": "value_error.missing"}
            ]
        }

        with patch.object(client._session, "post") as mock_post:
            mock_post.return_value = mock_response(400, validation_error)

            with pytest.raises(AIProxyValidationError) as exc_info:
                client.recognize_food(
                    image_bytes=b"fake-image",
                    content_type="image/jpeg",
                )

            assert "validation error 400" in str(exc_info.value).lower()

    def test_200_with_success_payload_returns_ok_true(self, client, mock_response):
        """
        Test: AI Proxy возвращает 200 + success payload
        Expected: AIProxyResult(ok=True)
        """
        success_payload = {
            "items": [{"name": "Банан", "grams": 120, "calories": 108}],
            "totals": {"calories": 108, "protein": 1.3, "fat": 0.4, "carbohydrates": 27},
            "meta": {"request_id": "test-req", "model": "gpt-5-image-mini"},
        }

        with patch.object(client._session, "post") as mock_post:
            mock_post.return_value = mock_response(200, success_payload)

            result = client.recognize_food(
                image_bytes=b"fake-image",
                content_type="image/jpeg",
                request_id="test-req",
            )

            assert isinstance(result, AIProxyResult)
            assert result.ok is True
            assert result.status_code == 200
            assert result.payload == success_payload
            assert len(result.payload["items"]) == 1

    def test_401_raises_authentication_error(self, client, mock_response):
        """
        Test: AI Proxy возвращает 401 (invalid secret)
        Expected: AIProxyAuthenticationError exception
        """
        with patch.object(client._session, "post") as mock_post:
            mock_post.return_value = mock_response(401, {"detail": "Invalid API key"})

            with pytest.raises(AIProxyAuthenticationError) as exc_info:
                client.recognize_food(
                    image_bytes=b"fake-image",
                    content_type="image/jpeg",
                )

            assert "auth error 401" in str(exc_info.value).lower()

    def test_500_raises_server_error(self, client, mock_response):
        """
        Test: AI Proxy возвращает 500 (internal error)
        Expected: AIProxyServerError exception
        """
        with patch.object(client._session, "post") as mock_post:
            mock_post.return_value = mock_response(500, {"detail": "Internal error"})

            with pytest.raises(AIProxyServerError) as exc_info:
                client.recognize_food(
                    image_bytes=b"fake-image",
                    content_type="image/jpeg",
                )

            assert "server error 500" in str(exc_info.value).lower()

    def test_200_with_error_code_returns_structured_error(self, client, mock_response):
        """
        Test: AI Proxy возвращает 200 + error_code (legacy compat mode)
        Expected: AIProxyResult(ok=False) — error_code всегда означает бизнес-ошибку
        """
        error_in_200 = {
            "error_code": "EMPTY_RESULT",
            "user_title": "Не удалось распознать блюдо",
            "user_message": "Попробуйте сфотографировать еду ближе при хорошем освещении.",
            "user_actions": ["retake"],
            "allow_retry": False,
            "trace_id": "test-trace-id",
        }

        with patch.object(client._session, "post") as mock_post:
            mock_post.return_value = mock_response(200, error_in_200)

            result = client.recognize_food(
                image_bytes=b"fake-image",
                content_type="image/jpeg",
            )

            # Даже с HTTP 200, если есть error_code → ok=False
            assert isinstance(result, AIProxyResult)
            assert result.ok is False
            assert result.status_code == 200
            assert result.payload["error_code"] == "EMPTY_RESULT"
