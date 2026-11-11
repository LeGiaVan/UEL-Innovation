import json
import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")


def test_browser_chat_renders_citation_and_escapes_answer():
    html = (Path(__file__).parents[2] / "app" / "web" / "index.html").read_text(
        encoding="utf-8-sig"
    )
    executable = os.environ.get("BROWSER_EXECUTABLE")
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=executable)
        page = browser.new_page()
        page.route(
            "http://chat.test/",
            lambda route: route.fulfill(status=200, content_type="text/html", body=html),
        )

        def modules(route):
            assert route.request.headers["x-api-key"] == "test-key"
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"modules": [{"code": "khao_khi", "name": "Khảo khí"}]}),
            )

        def chat(route):
            assert route.request.headers["x-api-key"] == "test-key"
            assert route.request.post_data_json["message"] == "Hello"
            assert route.request.post_data_json["module_code"] == "khao_khi"
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "conversation_id": "5a7f17f0-b0f6-4aad-bc0b-f9b7d5e970a1",
                        "status": "answered",
                        "answer": "<img src=x onerror=alert(1)>",
                        "citations": [{"kind": "document_code", "value": "TL03<img src=x>"}],
                        "support_contact": None,
                        "contact_information": None,
                        "online_channel": "javascript:alert(1)",
                    }
                ),
            )

        page.route("http://chat.test/v1/modules", modules)
        page.route("http://chat.test/v1/chat", chat)
        page.goto("http://chat.test/")
        page.locator("#key").fill("test-key")
        page.locator("#loadModules").click()
        page.locator("#module").select_option("khao_khi")
        page.locator("#message").fill("Hello")
        page.locator("#send").click()
        page.get_by_text("document_code: TL03", exact=False).wait_for()
        assert page.locator("#messages img").count() == 0
        assert page.locator("#messages a").count() == 0
        assert "javascript:alert(1)" in page.locator("#messages").inner_text()
        assert "<img src=x onerror=alert(1)>" in page.locator("#messages").inner_text()
        browser.close()
