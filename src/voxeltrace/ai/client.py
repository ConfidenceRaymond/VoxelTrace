"""Client skeleton for a local OpenAI-compatible server (e.g. vLLM on the GB10).

There is deliberately no cloud fallback. Non-loopback endpoints are refused
unless ``allow_remote=True`` is passed explicitly. No API key is required.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from voxeltrace.config import Settings, get_settings, is_loopback_url
from voxeltrace.schemas import AIServerStatus

SYSTEM_PROMPT = (
    "You are VoxelTrace, a research assistant for quantitative PET analysis. "
    "Interpret ONLY the structured evidence provided. Never invent, estimate or "
    "alter quantitative measurements. State uncertainty and QC concerns. "
    "This is a research prototype and not for clinical diagnosis."
)


class LocalAIUnavailableError(RuntimeError):
    """Raised when the local model server cannot be reached or returns an error."""


class LocalAIClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        model: str | None = None,
        timeout_s: float | None = None,
        api_key: str | None = None,
        allow_remote: bool | None = None,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        s = settings or get_settings()
        self.base_url = (base_url or s.ai_base_url).rstrip("/")
        self.model = model if model is not None else s.ai_model
        allow = s.ai_allow_remote if allow_remote is None else allow_remote
        if not allow and not is_loopback_url(self.base_url):
            raise ValueError(f"refusing non-local AI endpoint {self.base_url!r}")
        if api_key is None and s.ai_api_key is not None:
            api_key = s.ai_api_key.get_secret_value()
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout_s if timeout_s is not None else s.ai_timeout_s,
            transport=transport,
            trust_env=False,  # never route local traffic through a system proxy
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> LocalAIClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def list_models(self) -> list[str]:
        """Return model ids from ``GET /models``; raise LocalAIUnavailableError on failure."""
        try:
            resp = self._http.get("/models")
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LocalAIUnavailableError(
                f"local AI server at {self.base_url} unavailable: {exc}"
            ) from exc
        return [m["id"] for m in payload.get("data", []) if "id" in m]

    def health(self) -> AIServerStatus:
        """Probe the server. Never raises for connectivity problems."""
        try:
            models = self.list_models()
        except LocalAIUnavailableError as exc:
            return AIServerStatus(base_url=self.base_url, reachable=False, error=str(exc))
        return AIServerStatus(base_url=self.base_url, reachable=True, models=models)

    def build_reasoning_request(
        self, evidence: dict[str, Any], question: str, *, model: str | None = None
    ) -> dict[str, Any]:
        """Build a chat-completions payload grounding the model in structured evidence."""
        return {
            "model": model or self.model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "STRUCTURED EVIDENCE (computed deterministically):\n"
                        f"{json.dumps(evidence, indent=2, sort_keys=True)}\n\n"
                        f"QUESTION: {question}"
                    ),
                },
            ],
        }

    def reason_structured(self, evidence: dict[str, Any], question: str) -> dict[str, Any]:
        """Evidence-grounded reasoning. Planned for a later milestone."""
        raise NotImplementedError(
            "structured reasoning is not implemented in milestone 0/1; "
            "use build_reasoning_request() to inspect the planned payload"
        )
