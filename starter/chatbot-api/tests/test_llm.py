from __future__ import annotations

from app.services.llm import chat_complete, options_from_settings, parse_rule_id


class _Resp:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "content": [{"type": "text", "text": '{"rule_id": "khao_khi.han-phuc-khao"}'}],
            "usage": {"input_tokens": 11, "output_tokens": 7},
        }


class _Client:
    last = {}

    def __init__(self, *args, **kwargs) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, headers=None, json=None):
        _Client.last = {"url": url, "headers": headers, "json": json}
        return _Resp()


def test_parse_rule_id_json_fence() -> None:
    allowed = {"khao_khi.han-phuc-khao"}
    raw = '```json\n{"rule_id": "khao_khi.han-phuc-khao"}\n```'
    assert parse_rule_id(raw, allowed) == "khao_khi.han-phuc-khao"


def test_anthropic_messages_api(monkeypatch) -> None:
    monkeypatch.setattr("app.services.llm.httpx.Client", _Client)
    text, tokens = chat_complete(
        api_key="sk-ant-test",
        base_url="",
        model="claude-haiku-5-5",
        provider="anthropic",
        messages=[
            {"role": "system", "content": "Chỉ JSON"},
            {"role": "user", "content": "hỏi"},
        ],
        max_tokens=80,
    )
    assert "han-phuc-khao" in text
    assert tokens == 18
    assert _Client.last["url"].endswith("/v1/messages")
    assert _Client.last["headers"]["x-api-key"] == "sk-ant-test"
    assert _Client.last["json"]["system"] == "Chỉ JSON"
    assert _Client.last["json"]["messages"][0]["role"] == "user"
    assert "temperature" not in _Client.last["json"]
    assert _Client.last["json"]["thinking"] == {"type": "disabled"}


class _LimitClient:
    calls = 0

    def __init__(self, *args, **kwargs) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, headers=None, json=None):
        _LimitClient.calls += 1
        n = _LimitClient.calls

        class _Resp:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                if n == 1:
                    return {
                        "content": [{"type": "text", "text": "Yêu cầu thấp hơn,"}],
                        "stop_reason": "max_tokens",
                        "usage": {"input_tokens": 10, "output_tokens": 8},
                    }
                return {
                    "content": [{"type": "text", "text": " CEFR B1."}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 12, "output_tokens": 4},
                }

        return _Resp()


def test_anthropic_continues_on_max_tokens(monkeypatch) -> None:
    _LimitClient.calls = 0
    monkeypatch.setattr("app.services.llm.httpx.Client", _LimitClient)
    text, tokens = chat_complete(
        api_key="sk-ant-test",
        model="claude-haiku-5-5",
        provider="anthropic",
        messages=[{"role": "user", "content": "hỏi"}],
        max_tokens=32,
        continue_on_limit=True,
    )
    assert text == "Yêu cầu thấp hơn, CEFR B1."
    assert _LimitClient.calls == 2
    assert tokens == 34


def test_options_detect_anthropic_from_key() -> None:
    class S:
        llm_api_key = "sk-ant-x"
        llm_provider = ""
        llm_model = "claude-haiku-5-5"
        llm_base_url = ""
        llm_timeout_seconds = 45
        llm_max_retries = 1

    opts = options_from_settings(S())
    assert opts["provider"] == "anthropic"
