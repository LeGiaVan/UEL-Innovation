from __future__ import annotations

import json
import logging
from typing import Any

from app.agent.llm import LlmRequest, LlmResponse, LlmResponseError, LlmServerError, LlmTimeoutError

_LOG = logging.getLogger(__name__)


class GeminiLlm:
    def __init__(self, *, api_key: str, model: str, timeout_seconds: float) -> None:
        if not api_key:
            raise LlmServerError("LLM_API_KEY is empty")
        self._api_key = api_key
        self._model = model
        self._timeout_ms = max(45_000, int(timeout_seconds * 1000))
        self._client: Any = None

    def complete(self, request: LlmRequest) -> LlmResponse:
        try:
            from google import genai  # type: ignore[import-untyped,unused-ignore]
            from google.genai import types  # type: ignore[import-untyped,unused-ignore]
        except ImportError as exc:
            raise LlmServerError("google-genai is not installed; pip install -e '.[llm]'") from exc

        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        model_id = self._model.removeprefix("models/")

        system_parts = [item.content for item in request.messages if item.role == "system"]
        user_parts = [item.content for item in request.messages if item.role == "user"]
        if user_parts:
            contents = "\n\n".join(user_parts)
        else:
            contents = "\n\n".join(item.content for item in request.messages)
        timeout_ms = self._timeout_ms
        if request.timeout_seconds is not None:
            timeout_ms = max(10_000, int(request.timeout_seconds * 1000))
        config_kwargs: dict[str, Any] = {
            "http_options": types.HttpOptions(timeout=timeout_ms),
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
        }
        if system_parts:
            config_kwargs["system_instruction"] = "\n\n".join(system_parts)
        thinking = getattr(types, "ThinkingConfig", None)
        if thinking is not None:
            config_kwargs["thinking_config"] = thinking(thinking_budget=0)
        if request.json_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = request.json_schema
        try:
            result = self._client.models.generate_content(
                model=model_id,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:
            message = str(exc).casefold()
            if "too short" in message:
                raise LlmResponseError(str(exc)) from exc
            if (
                "504" in message
                or "deadline_exceeded" in message
                or "deadline expired" in message
                or "timeout" in message
            ):
                raise LlmTimeoutError(str(exc)) from exc
            if "invalid_argument" in message:
                raise LlmResponseError(str(exc)) from exc
            if "404" in message or "not_found" in message or "no longer available" in message:
                raise LlmResponseError(
                    f"Gemini model '{model_id}' is not available. "
                    "Set LLM_MODEL (default gemini-3.8-flash)."
                ) from exc
            if any(token in message for token in ("500", "502", "503", "unavailable")):
                raise LlmServerError(str(exc)) from exc
            raise LlmServerError(str(exc)) from exc
        text = _response_text(result)
        if not text:
            reason = _finish_reason(result)
            raise LlmResponseError(f"Gemini returned empty text ({reason})")
        parsed: dict[str, Any] | None = None
        if request.json_schema is not None:
            try:
                loaded = json.loads(text)
            except json.JSONDecodeError as exc:
                raise LlmResponseError("Gemini returned invalid JSON") from exc
            if isinstance(loaded, dict):
                parsed = loaded
        return LlmResponse(text=text, parsed=parsed)


def _response_text(result: Any) -> str:
    try:
        direct = result.text
        if direct:
            return str(direct).strip()
    except Exception as exc:
        _LOG.debug("gemini result.text unavailable: %s", exc)
    chunks: list[str] = []
    for candidate in getattr(result, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            piece = getattr(part, "text", None)
            if piece:
                chunks.append(str(piece))
    return "\n".join(chunks).strip()


def _finish_reason(result: Any) -> str:
    candidates = getattr(result, "candidates", None) or []
    if not candidates:
        return "no_candidates"
    reason = getattr(candidates[0], "finish_reason", None)
    return str(reason or "unknown")
