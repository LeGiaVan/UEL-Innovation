import json
import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")


def test_browser_admin_onboard_wizard_and_tabs():
    html = (Path(__file__).parents[2] / "app" / "web" / "admin.html").read_text(
        encoding="utf-8-sig"
    )
    executable = os.environ.get("BROWSER_EXECUTABLE")
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=executable)
        page = browser.new_page()
        page.route(
            "http://admin.test/admin",
            lambda route: route.fulfill(status=200, content_type="text/html", body=html),
        )
        page.route(
            "http://admin.test/v1/admin/tenants",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    [
                        {
                            "department_id": "phong_dao_tao",
                            "department_name": "Phòng Đào tạo",
                            "module_code": "dang_ky_hoc_phan",
                            "module_name": "Đăng ký học phần",
                            "profile": "generic",
                            "enabled": True,
                            "source_path": "data/phong_dao_tao/dang_ky_hoc_phan",
                            "source_present": True,
                            "has_prompt_pack": False,
                        }
                    ]
                ),
            ),
        )
        page.route(
            "http://admin.test/v1/admin/modules/phong_dao_tao/dang_ky_hoc_phan/bot",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                headers={"etag": '"abc"'},
                body=json.dumps(
                    {
                        "profile": "generic",
                        "prompt_pack": {
                            "role": "",
                            "constraints": "",
                            "glossary": {},
                            "answer_style": "",
                            "metadata_system": "",
                        },
                        "messages": {"greeting": "", "out_of_scope": "", "clarification": ""},
                        "retrieval": {"top_k": None, "score_threshold": None},
                        "routing_aliases": {},
                    }
                ),
            ),
        )
        page.goto("http://admin.test/admin")
        page.locator("#onboardWizard").wait_for()
        page.locator("#departmentName").fill("Phòng Đào tạo")
        page.locator("#moduleName").fill("Đăng ký học phần")
        page.locator("#toFiles").click()
        page.locator("#inspectTemplates").wait_for()
        page.locator("#dropT1").wait_for()
        page.locator("#tabPack").click()
        page.locator("#role").wait_for()
        page.locator("#tabOnboard").click()
        page.locator("#adminKey").fill("admin-secret-with-enough-length")
        page.locator("#moduleCards .mod-card").wait_for()
        page.locator("#moduleCards .mod-card").click()
        page.locator("#role").wait_for()
        browser.close()
