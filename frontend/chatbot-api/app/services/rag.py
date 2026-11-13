from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from urllib.parse import urljoin

import httpx
from fastapi import HTTPException

# Lounge room id / mode → UEL-Innovation tenant + module. Overlay via CHATBOT_RAG_ROUTES.
DEFAULT_RAG_ROUTES: dict[str, dict[str, Any]] = {
    "dbcl": {
        "department_id": "bao_dam_chat_luong",
        "modules": {"module_1": "khao_khi"},
    }
}
RAG_ROUTES = DEFAULT_RAG_ROUTES


def merged_rag_routes(overlay: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    merged = {key: dict(value) for key, value in DEFAULT_RAG_ROUTES.items()}
    for department, spec in (overlay or {}).items():
        if isinstance(spec, dict):
            merged[str(department)] = spec
    return merged


def map_rag_target(
    department: str, mode: str, routes: dict[str, dict[str, Any]] | None = None
) -> tuple[str, str] | None:
    table = routes if routes is not None else DEFAULT_RAG_ROUTES
    route = table.get(department)
    if not route:
        return None
    module = (route.get("modules") or {}).get(mode)
    if not module:
        return None
    return str(route["department_id"]), str(module)


def citations_for_frontend(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index, item in enumerate(raw or [], start=1):
        kind = str(item.get("kind") or "")
        value = str(item.get("value") or "").strip()
        if not value or kind == "chunk_id":
            continue
        source_kind = "faq" if kind == "question_code" else "document"
        out.append(
            {
                "index": index,
                "source_kind": source_kind,
                "source": value,
                "document_name": value,
            }
        )
    return out


def contact_line(data: dict[str, Any]) -> str | None:
    contact = " | ".join(
        part
        for part in (
            data.get("support_contact"),
            data.get("contact_information"),
            data.get("online_channel"),
        )
        if part
    )
    return contact or None


def translate_rag_event(
    event_name: str,
    payload: dict[str, Any],
    *,
    mode: str,
    user_message: str,
    conversation_id: str,
) -> dict[str, Any] | None:
    name = (event_name or payload.get("type") or "message").strip()
    if name == "token":
        return {"type": "token", "text": str(payload.get("text") or "")}
    if name == "status":
        return {
            "type": "status",
            "label": str(payload.get("label") or ""),
            "stage": payload.get("stage"),
        }
    if name == "error":
        return {"type": "error", "message": str(payload.get("detail") or payload.get("message") or "Lỗi RAG")}
    if name == "done":
        answer = str(payload.get("answer") or payload.get("response") or "")
        return {
            "type": "done",
            "response": answer,
            "conversation_id": conversation_id,
            "user_message": user_message,
            "resolved_mode": mode,
            "citations": citations_for_frontend(payload.get("citations")),
            "contact_info": contact_line(payload),
            "interactive": None,
            "provider": "rag",
        }
    if payload.get("type"):
        return payload
    return None


def iter_named_sse(chunks: Iterator[bytes]) -> Iterator[tuple[str, dict[str, Any]]]:
    buffer = ""
    for raw in chunks:
        buffer += raw.decode("utf-8", errors="replace")
        while True:
            cut = buffer.find("\r\n\r\n")
            width = 4
            if cut < 0:
                cut = buffer.find("\n\n")
                width = 2
            if cut < 0:
                break
            block, buffer = buffer[:cut], buffer[cut + width :]
            event_name = "message"
            data_lines: list[str] = []
            for line in block.splitlines():
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
            if not data_lines:
                continue
            blob = "\n".join(data_lines)
            if blob == "[DONE]":
                continue
            yield event_name, json.loads(blob)


class RagAnswerProvider:
    """Gọi FastAPI RAG hiện tại. Không thay graph/Qdrant của UEL-Innovation."""

    def __init__(self, settings: Any) -> None:
        self.base = str(getattr(settings, "rag_base_url", "http://127.0.0.1:8000")).rstrip("/")
        self.api_key = str(getattr(settings, "rag_api_key", "") or "")
        self.timeout = float(getattr(settings, "rag_timeout_seconds", 90))
        self.routes = merged_rag_routes(getattr(settings, "rag_routes", None))

    def answer(self, department: str, mode: str, message: str) -> str:
        return self.complete(department, mode, message)["response"]

    def complete(
        self,
        department: str,
        mode: str,
        message: str,
        *,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        done = None
        for event in self.iter_sse(
            department, mode, message, conversation_id=conversation_id
        ):
            if event.get("type") == "done":
                done = event
        if done is None:
            raise HTTPException(502, "RAG không trả sự kiện done.")
        return {
            "response": done.get("response") or "",
            "citations": done.get("citations") or [],
            "contact_info": done.get("contact_info"),
            "status": "answered",
        }

    def iter_sse(
        self,
        department: str,
        mode: str,
        message: str,
        *,
        conversation_id: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        mapped = map_rag_target(department, mode, self.routes)
        if mapped is None:
            from app.services.providers import StubAnswerProvider

            text = StubAnswerProvider().answer(department, mode, message)
            for index in range(0, len(text), 24):
                yield {"type": "token", "text": text[index : index + 24]}
            yield {
                "type": "done",
                "response": text,
                "conversation_id": conversation_id,
                "user_message": message,
                "resolved_mode": mode,
                "citations": [],
                "contact_info": None,
                "interactive": None,
                "provider": "stub",
            }
            return
        _department_id, module_code = mapped
        payload: dict[str, Any] = {"message": message, "module_code": module_code}
        if conversation_id:
            payload["conversation_id"] = conversation_id
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
            "Accept": "text/event-stream",
        }
        url = urljoin(self.base + "/", "v1/chat/stream")
        timeout = httpx.Timeout(self.timeout, connect=10.0)
        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code >= 400:
                        detail = response.read().decode("utf-8", errors="replace")
                        self._raise_http(response.status_code, detail)
                    for event_name, data in iter_named_sse(response.iter_bytes()):
                        event = translate_rag_event(
                            event_name,
                            data,
                            mode=mode,
                            user_message=message,
                            conversation_id=conversation_id or "",
                        )
                        if event:
                            yield event
        except HTTPException:
            raise
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Không kết nối RAG tại {self.base}: {exc}") from None

    @staticmethod
    def _raise_http(code: int, detail: str) -> None:
        if code in {401, 403}:
            raise HTTPException(
                502,
                "BFF không gọi được RAG (sai X-API-Key hoặc module chưa có trong API_CLIENTS).",
            )
        if code == 504:
            raise HTTPException(504, "RAG hết thời gian xử lý.")
        raise HTTPException(502, f"RAG HTTP {code}: {detail[:300]}")
