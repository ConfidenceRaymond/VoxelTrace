import httpx
import pytest

import voxeltrace
from voxeltrace.ai import LocalAIClient, LocalAIUnavailableError
from voxeltrace.config import Settings, get_settings


def test_package_metadata():
    assert voxeltrace.__version__ == "0.4.0"
    assert "NOT FOR CLINICAL DIAGNOSIS" in voxeltrace.DISCLAIMER


def test_default_settings_are_local():
    s = get_settings()
    assert s.ai_base_url == "http://127.0.0.1:8000/v1"
    assert s.ai_allow_remote is False
    assert s.ai_api_key is None


def test_remote_endpoint_rejected_by_default():
    with pytest.raises(ValueError):
        Settings(ai_base_url="https://api.example.com/v1")
    with pytest.raises(ValueError):
        LocalAIClient("https://api.example.com/v1")


def test_no_auth_header_by_default():
    with LocalAIClient() as client:
        assert "authorization" not in client._http.headers


def test_health_fails_cleanly_when_no_server():
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with LocalAIClient(transport=httpx.MockTransport(refuse)) as client:
        status = client.health()
        assert status.reachable is False
        assert status.error
        with pytest.raises(LocalAIUnavailableError):
            client.list_models()


def test_health_lists_models():
    def ok(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "local-model"}]})

    with LocalAIClient(transport=httpx.MockTransport(ok)) as client:
        status = client.health()
    assert status.reachable is True
    assert status.models == ["local-model"]


def test_reasoning_is_placeholder():
    with LocalAIClient() as client:
        payload = client.build_reasoning_request({"suv_max": 1.0}, "Summarise.")
        assert payload["temperature"] == 0.0
        assert "suv_max" in payload["messages"][1]["content"]
        with pytest.raises(NotImplementedError):
            client.reason_structured({}, "q")
