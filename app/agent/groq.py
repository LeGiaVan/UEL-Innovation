from __future__ import annotations

import json
from typing import Any

import httpx

from app.agent.llm import LlmRequest, LlmResponse, LlmResponseError, LlmServerError, LlmTimeoutError

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
RETIRED_GROQ_MODELS = frozenset(
    {
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "llama3-70b-8192",
        "llama3-8b-8192",
    }
)
STRICT_JSON_MODELS = frozenset(
    {
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-safeguard-20b",
        "qwen/qwen3.8-27b",
    }
)


class GroqLlm:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        base_url: str = GROQ_BASE_URL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise LlmServerError(
                "LLM_API_KEY is empty. Create a Groq key at https://console.groq.com/keys"
            )
        self._model = model or DEFAULT_GROQ_MODEL
        timeout = max(10.0, float(timeout_seconds))
        self._timeout = timeout
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
            transport=transport,
        )

    def complete(self, request: LlmRequest) -> LlmResponse:
        timeout = self._timeout
        if request.timeout_seconds is not None:
            timeout = max(10.0, float(request.timeout_seconds))
        payload = _payload(self._model, request)
        try:
            response = self._client.post("/chat/completions", json=payload, timeout=timeout)
        except httpx.TimeoutException as exc:
            raise LlmTimeoutError(str(exc)) from exc
        except httpx.RequestError as exc:
            raise LlmServerError(str(exc)) from exc
        return _parse_response(response, request.json_schema is not None, self._model)


def resolve_groq_model(model: str) -> str:
    folded = model.strip()
    if (
        not folded
        or folded.startswith("gemini")
        or folded.startswith("models/")
        or folded in RETIRED_GROQ_MODELS
    ):
        return DEFAULT_GROQ_MODEL
    return folded


def _payload(model: str, request: LlmRequest) -> dict[str, Any]:
    messages = [{"role": item.role, "content": item.content} for item in request.messages]
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0 if request.json_schema is not None else 0.2,
        "max_tokens": 256 if request.json_schema is not None else 2048,
    }
    if model.startswith("openai/gpt-oss"):
        body["reasoning_effort"] = "low"
    if request.json_schema is None:
        return body
    if model in STRICT_JSON_MODELS:
        schema = dict(request.json_schema)
        schema.setdefault("additionalProperties", False)
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": request.purpose,
                "strict": True,
                "schema": schema,
            },
        }
        return body
    body["response_format"] = {"type": "json_object"}
    if messages and messages[0]["role"] == "system":
        messages[0]["content"] = (
            f"{messages[0]['content']}\nTrả đúng một JSON object hợp lệ, không markdown."
        )
    return body


def _parse_response(
    response: httpx.Response, expect_json: bool, model: str
) -> LlmResponse:
    status = response.status_code
    body = response.text
    preview = body[:400]
    if status in {408, 504}:
        raise LlmTimeoutError(f"{status} {preview}")
    if status == 429:
        raise LlmServerError(f"429 rate limit {preview}")
    if status in {401, 403}:
        raise LlmResponseError("Groq API key bị từ chối. Kiểm tra LLM_API_KEY.")
    if status == 404:
        raise LlmResponseError(
            f"Groq model '{model}' không tồn tại. Đặt LLM_MODEL (mặc định {DEFAULT_GROQ_MODEL})."
        )
    if status in {500, 502, 503}:
        raise LlmServerError(f"{status} {preview}")
    if status >= 400:
        raise LlmResponseError(f"{status} {preview}")
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise LlmResponseError("Groq returned invalid JSON envelope") from exc
    text = _choice_text(data)
    if not text:
        raise LlmResponseError("Groq returned empty text")
    parsed: dict[str, Any] | None = None
    if expect_json:
        try:
            loaded = json.loads(_strip_fences(text))
        except json.JSONDecodeError as exc:
            raise LlmResponseError("Groq returned invalid JSON") from exc
        if isinstance(loaded, dict):
            parsed = loaded
    return LlmResponse(text=text, parsed=parsed)


def _choice_text(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = (choices[0] or {}).get("message") or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        if parts:
            return "\n".join(parts)
    return ""


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned
    cleaned = cleaned.removeprefix("```").strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].lstrip()
    if cleaned.endswith("```"):
        cleaned = cleaned[: cleaned.rfind("```")].rstrip()
    return cleaned
