from __future__ import annotations

import json
import logging
import re
import time

import httpx

log = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def options_from_settings(settings) -> dict:
    key = getattr(settings, "llm_api_key", "") or ""
    provider = (getattr(settings, "llm_provider", "") or "").strip().lower()
    if not provider and str(key).startswith("sk-ant-"):
        provider = "anthropic"
    return {
        "api_key": key,
        "base_url": getattr(settings, "llm_base_url", "") or "",
        "model": getattr(settings, "llm_model", "") or "",
        "provider": provider,
        "timeout": float(getattr(settings, "llm_timeout_seconds", 45) or 45),
        "max_retries": int(getattr(settings, "llm_max_retries", 1) or 0),
    }


def chat_complete(
    *,
    api_key: str,
    base_url: str = "",
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 800,
    provider: str = "",
    timeout: float = 45,
    max_retries: int = 1,
) -> tuple[str, int]:
    if not api_key:
        return "", 0
    kind = (provider or "").strip().lower()
    if not kind and api_key.startswith("sk-ant-"):
        kind = "anthropic"
    if kind in {"anthropic", "claude"}:
        return _anthropic_complete(
            api_key=api_key,
            base_url=base_url,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout,
            max_retries=max_retries,
        )
    return _openai_complete(
        api_key=api_key,
        base_url=base_url or "https://api.openai.com/v1",
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=max_retries,
    )


def _split_system(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    system = "\n\n".join(m.get("content") or "" for m in messages if m.get("role") == "system").strip()
    rest = [{"role": m["role"], "content": m.get("content") or ""} for m in messages if m.get("role") != "system"]
    if rest and rest[0]["role"] != "user":
        rest = [{"role": "user", "content": rest[0]["content"]}] + rest[1:]
    if not rest:
        rest = [{"role": "user", "content": " "}]
    return system, rest


def _post_with_retries(url: str, *, headers: dict, payload: dict, timeout: float, max_retries: int) -> dict:
    last_exc: Exception | None = None
    attempts = max(1, int(max_retries) + 1)
    for attempt in range(attempts):
        try:
            with httpx.Client(timeout=timeout) as client:
                res = client.post(url, headers=headers, json=payload)
            if res.status_code in {429, 500, 502, 503, 529} and attempt + 1 < attempts:
                time.sleep(0.6 * (attempt + 1))
                continue
            if res.status_code >= 400:
                log.warning("LLM HTTP %s: %s", res.status_code, (res.text or "")[:400])
            res.raise_for_status()
            return res.json()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt + 1 < attempts:
                time.sleep(0.6 * (attempt + 1))
                continue
            raise
    raise last_exc or RuntimeError("LLM request failed")


def _openai_complete(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout: float,
    max_retries: int,
) -> tuple[str, int]:
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens}
    try:
        data = _post_with_retries(url, headers=headers, payload=payload, timeout=timeout, max_retries=max_retries)
        text = (((data.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
        usage = data.get("usage") or {}
        tokens = int(usage.get("total_tokens") or 0)
        return text.strip(), tokens
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM OpenAI-compatible failed: %s", exc)
        return "", 0


def _anthropic_complete(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout: float,
    max_retries: int,
) -> tuple[str, int]:
    raw = (base_url or "").rstrip("/")
    if not raw or "openai.com" in raw:
        url = ANTHROPIC_URL
    elif raw.endswith("/messages"):
        url = raw
    else:
        url = raw + "/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    system, rest = _split_system(messages)
    # Haiku 5.5+: temperature/top_p/top_k → 400. Tắt thinking để JSON rule_id không bị nuốt.
    payload: dict = {
        "model": model,
        "max_tokens": max(max_tokens, 256),
        "thinking": {"type": "disabled"},
        "output_config": {"effort": "low"},
        "messages": rest,
    }
    if system:
        payload["system"] = system
    try:
        data = _post_with_retries(url, headers=headers, payload=payload, timeout=timeout, max_retries=max_retries)
        blocks = data.get("content") or []
        text = "".join(b.get("text") or "" for b in blocks if isinstance(b, dict) and b.get("type") in {None, "text"})
        usage = data.get("usage") or {}
        tokens = int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0)
        return text.strip(), tokens
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM Anthropic failed: %s", exc)
        return "", 0


def parse_rule_id(raw: str, allowed: set[str]) -> str | None:
    text = (raw or "").strip()
    if not text or text.lower() in {"null", "none"}:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
        cand = data.get("rule_id") if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)+", text, re.I)
        cand = match.group(0) if match else None
    if cand in allowed:
        return cand
    return None
