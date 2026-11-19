"""Copy starter/ vào 8 thư mục đơn vị. Không mang mô-đun / seed / regex demo."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "starter"

ROOMS = [
    ("phong-hanh-chinh", "hc", "HC", "Phòng Hành chính", "hc.chat.uel.edu.vn"),
    ("phong-tuyen-sinh-cong-tac-sinh-vien", "ctsv", "CTSV", "Phòng Tuyển sinh & Công tác sinh viên", "ctsv.chat.uel.edu.vn"),
    ("phong-dao-tao", "pdt", "PĐT", "Phòng Đào tạo", "pdt.chat.uel.edu.vn"),
    ("phong-quan-tri-tai-san", "qtts", "QTTS", "Phòng Quản trị tài sản", "qtts.chat.uel.edu.vn"),
    ("vien-quoc-te", "vqt", "VQT", "Viện Quốc tế", "vqt.chat.uel.edu.vn"),
    ("phong-nhan-su", "pns", "PNS", "Phòng Nhân sự", "pns.chat.uel.edu.vn"),
    ("phong-khoa-hoc-cong-nghe", "khcn", "KHCN", "Phòng Khoa học công nghệ", "khcn.chat.uel.edu.vn"),
    ("phong-bao-dam-chat-luong", "dbcl", "ĐBCL", "Phòng Bảo đảm chất lượng", "dbcl.chat.uel.edu.vn"),
]

SKIP_DIR = {
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "dist",
    ".git",
    ".mypy_cache",
    ".ruff_cache",
    "releases",
}
SKIP_FILE = {
    ".env",
    "gold_chat.last.json",
    "latency.last.json",
    ".DS_Store",
    "Thumbs.db",
    "_seed_rooms.py",
    "map_khao_khi.py",
}

ROOM_PERSONA = """greeting: |
  Xin chào. Tôi là trợ lý của đơn vị này.
out_of_scope: |
  Câu này ngoài phạm vi hỗ trợ của phòng.
clarification: |
  Bạn đang hỏi điều gì? Vui lòng nói rõ hơn.
handoff: |
  Việc này cần cán bộ hỗ trợ. Bạn dùng form bên dưới hoặc liên hệ đầu mối của phòng.
role: Trợ lý quy định của đơn vị
constraints: |
  Không bịa số ngày. Không trả dữ liệu cá nhân.
  Mốc thời gian chỉ nói theo File 04 đã nạp.
glossary: {}
answer_style: |
  Trả lời mạch lạc, đủ ý, như nhân viên phòng đang giải thích — không đọc máy.
  Dùng Markdown: **đậm** số liệu và điều kiện; bước thành danh sách; bảng khi so sánh.
routing_regex: []
cosine_threshold: 0.62
top_k: 6
"""


def _ignore(directory: str, names: list[str]) -> set[str]:
    skipped: set[str] = set()
    parent = Path(directory)
    drop_modules = parent.name == "modules" and parent.parent.name == "chatbot-data"
    for name in names:
        if name in SKIP_DIR or name in SKIP_FILE:
            skipped.add(name)
        elif name.endswith(".egg-info") or name.endswith(".pyc"):
            skipped.add(name)
        elif name.startswith(".env.") and name != ".env.example":
            skipped.add(name)
        elif drop_modules and name != ".gitkeep":
            skipped.add(name)
    return skipped


def _department_yaml(*, code: str, name: str, domain: str) -> str:
    return (
        f"id: {code}\n"
        f"name: {name}\n"
        f"domain: {domain}\n"
        "handoff_form_url: https://docs.google.com/forms/\n"
        "admins: []\n"
        "rate_limit:\n"
        "  chats_per_minute: 10\n"
        "  llm_tokens_per_day: 50000\n"
        "modules: []\n"
    )


def _stamp_env_example(path: Path, code: str) -> None:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    lines = []
    replaced = False
    for line in text.splitlines():
        if line.startswith("DEPARTMENT_ID="):
            lines.append(f"DEPARTMENT_ID={code}")
            replaced = True
        else:
            lines.append(line)
    if not replaced:
        lines.insert(0, f"DEPARTMENT_ID={code}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _stamp_compose(path: Path, code: str, domain: str) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    text = text.replace("    image: starter-app:latest\n", "")
    text = re.sub(r'"\d+:8000"', '"8000:8000"', text)
    text = re.sub(r'"\d+:6333"', '"6335:6333"', text)
    label = f"traefik.http.routers.{code}.rule=Host(`{domain}`)"
    if "traefik.http.routers." in text:
        text = re.sub(
            r"traefik\.http\.routers\.[a-z0-9]+\.rule=Host\(`[^`]+`\)",
            label,
            text,
        )
    elif 'ports:\n      - "8000:8000"' in text:
        text = text.replace(
            'ports:\n      - "8000:8000"',
            f'labels:\n      - {label}\n    ports:\n      - "8000:8000"',
        )
    path.write_text(text, encoding="utf-8")


def _stamp_identity(dest: Path, *, code: str, short: str, name: str) -> None:
    js_path = dest / "chatbot-web" / "src" / "config" / "department.js"
    if js_path.is_file():
        js_path.write_text(
            "/** Nhận diện giao diện dự phòng. Runtime lấy từ GET /api/auth/config (yaml). */\n"
            "export const department = {\n"
            f"  short: {json.dumps(short, ensure_ascii=False)},\n"
            f"  name: {json.dumps(name, ensure_ascii=False)},\n"
            f"  id: {json.dumps(code, ensure_ascii=False)},\n"
            "}\n\n"
            "export const navigation = {\n"
            "  chat: '/',\n"
            "  login: '/dang-nhap',\n"
            "  admin: '/quan-ly',\n"
            "}\n",
            encoding="utf-8",
        )
    json_path = dest / "chatbot-web" / "src" / "config" / "department.json"
    if json_path.parent.is_dir():
        json_path.write_text(
            json.dumps(
                {"short": short, "name": name, "id": code, "topics": []},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def _strip_demo_data(dest: Path) -> None:
    modules_dir = dest / "chatbot-data" / "modules"
    if modules_dir.is_dir():
        for child in modules_dir.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    persona = dest / "chatbot-api" / "configs" / "persona.yaml"
    persona.parent.mkdir(parents=True, exist_ok=True)
    persona.write_text(ROOM_PERSONA, encoding="utf-8")
    modules_yaml = dest / "chatbot-api" / "configs" / "modules.yaml"
    if modules_yaml.parent.is_dir():
        modules_yaml.write_text("modules: []\n", encoding="utf-8")


def fill_room(dest: Path, code: str, short: str, name: str, domain: str) -> None:
    yaml_path = dest / "chatbot-api" / "configs" / "department.yaml"
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(
        _department_yaml(code=code, name=name, domain=domain),
        encoding="utf-8",
    )
    _strip_demo_data(dest)
    env_ex = dest / ".env.example"
    if not env_ex.is_file():
        src = STARTER / ".env.example"
        if src.is_file():
            shutil.copy2(src, env_ex)
    _stamp_env_example(env_ex, code)
    api_env = dest / "chatbot-api" / ".env.example"
    if api_env.is_file():
        _stamp_env_example(api_env, code)
    _stamp_compose(dest / "docker-compose.yml", code, domain)
    _stamp_identity(dest, code=code, short=short, name=name)
    readme = dest / "README.md"
    banner = (
        f"# {name}\n\n"
        f"`DEPARTMENT_ID={code}` · `{domain}`\n\n"
        "Copy từ `starter/`. Điền `.env` + yaml + 5 Excel, rồi "
        "`docker compose -f docker-compose.prod.yml up -d --build`.\n\n"
        "Hướng dẫn: `docs/deploy.md` (gốc repo).\n"
    )
    readme.write_text(banner, encoding="utf-8")


def clone_one(folder: str, code: str, short: str, name: str, domain: str) -> Path:
    dest = ROOT / folder
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(STARTER, dest, ignore=_ignore, dirs_exist_ok=False)
    fill_room(dest, code, short, name, domain)
    return dest


def sanitize_existing() -> None:
    for folder, code, short, name, domain in ROOMS:
        dest = ROOT / folder
        if not dest.is_dir():
            continue
        fill_room(dest, code, short, name, domain)
        print(f"sanitized {folder} id={code} modules=[]")


def main() -> None:
    import sys

    if not STARTER.is_dir():
        raise SystemExit(f"missing {STARTER}")
    if "--sanitize" in sys.argv:
        sanitize_existing()
        return
    for folder, code, short, name, domain in ROOMS:
        dest = clone_one(folder, code, short, name, domain)
        print(f"cloned {dest.relative_to(ROOT)} id={code} domain={domain}")


if __name__ == "__main__":
    main()
