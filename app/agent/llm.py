from __future__ import annotations

import json
import re
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from app.core.config import Settings

LlmPurpose = Literal["routing", "metadata", "generate"]

DOCUMENT_CODE_RE = re.compile(r"\bTL0?\d+\b", re.IGNORECASE)
QUESTION_CODE_RE = re.compile(r"\b(?:I|II|III)\.\d+\.\d{3}\b")


class LlmError(Exception):
    """Base LLM failure."""


class LlmTimeoutError(LlmError):
    """Provider exceeded the configured timeout."""


class LlmServerError(LlmError):
    """Retryable provider 5xx / unavailable error."""


class LlmResponseError(LlmError):
    """Non-retryable empty or unusable model output."""


class LlmMessage(BaseModel):
    role: Literal["system", "user"]
    content: str


class LlmRequest(BaseModel):
    purpose: LlmPurpose
    messages: list[LlmMessage]
    json_schema: dict[str, Any] | None = None
    timeout_seconds: float | None = None


class LlmResponse(BaseModel):
    text: str
    parsed: dict[str, Any] | None = None


class LlmClient(Protocol):
    def complete(self, request: LlmRequest) -> LlmResponse: ...


class FakeLlm:
    """Deterministic LLM for unit tests. Never opens a network connection."""

    def __init__(
        self,
        *,
        routing_scope: str = "answer_allowed",
        metadata: dict[str, Any] | None = None,
        generate_text: str | None = None,
        fail: LlmError | None = None,
        fail_on: set[LlmPurpose] | None = None,
    ) -> None:
        self.routing_scope = routing_scope
        self.metadata = metadata or {
            "training_system": "unknown",
            "topic": "other",
            "is_fee_question": False,
        }
        self.generate_text = generate_text
        self.fail = fail
        self.fail_on = fail_on
        self.calls: list[LlmPurpose] = []
        self.requests: list[LlmRequest] = []

    def complete(self, request: LlmRequest) -> LlmResponse:
        self.calls.append(request.purpose)
        self.requests.append(request)
        if self.fail is not None and (self.fail_on is None or request.purpose in self.fail_on):
            raise self.fail
        if request.purpose == "routing":
            parsed = {"scope_type": self.routing_scope}
            return LlmResponse(text=json.dumps(parsed), parsed=parsed)
        if request.purpose == "metadata":
            return LlmResponse(text=json.dumps(self.metadata), parsed=dict(self.metadata))
        text = self.generate_text or _default_generate(request)
        return LlmResponse(text=text)


class RetryingLlm:
    def __init__(self, inner: LlmClient, *, max_retries: int) -> None:
        self._inner = inner
        self._max_retries = max_retries

    def complete(self, request: LlmRequest) -> LlmResponse:
        attempts = self._max_retries + 1
        last: LlmError | None = None
        for _ in range(attempts):
            try:
                return self._inner.complete(request)
            except LlmTimeoutError:
                raise
            except LlmServerError as exc:
                detail = str(exc).casefold()
                if any(
                    token in detail
                    for token in ("429", "rate limit", "503", "unavailable", "high demand")
                ):
                    raise
                last = exc
        assert last is not None
        raise last


def load_llm(settings: Settings) -> LlmClient:
    if settings.llm_provider == "fake":
        return FakeLlm()
    api_key = settings.llm_api_key.get_secret_value()
    if settings.llm_provider == "groq":
        from app.agent.groq import GroqLlm, resolve_groq_model

        inner: LlmClient = GroqLlm(
            api_key=api_key,
            model=resolve_groq_model(settings.llm_model),
            timeout_seconds=settings.llm_timeout_seconds,
        )
    else:
        from app.agent.gemini import GeminiLlm

        inner = GeminiLlm(
            api_key=api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return RetryingLlm(inner, max_retries=settings.llm_max_retries)


def _default_generate(request: LlmRequest) -> str:
    blob = " ".join(item.content for item in request.messages)
    documents = DOCUMENT_CODE_RE.findall(blob)
    questions = QUESTION_CODE_RE.findall(blob)
    cite = documents[0] if documents else (questions[0] if questions else "")
    if not cite:
        return "Theo dữ liệu đã duyệt trong ngữ cảnh."
    return f"Theo dữ liệu đã duyệt trong ngữ cảnh. Nguồn: {cite}."
