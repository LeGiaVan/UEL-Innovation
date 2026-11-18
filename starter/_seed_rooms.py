"""One-off helper used while scaffolding P0. Safe to delete later."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STARTER = Path(__file__).resolve().parent
SKIP = {"node_modules", "__pycache__", ".pytest_cache", "dist", ".venv"}

ROOMS = [
    {
        "dir": "phong-hanh-chinh",
        "id": "hc",
        "name": "Phòng Hành chính",
        "short": "HC",
        "domain": "hc.chat.uel.edu.vn",
        "module": "hanh_chinh",
        "module_name": "Hành chính",
    },
    {
        "dir": "phong-tuyen-sinh-cong-tac-sinh-vien",
        "id": "ctsv",
        "name": "Phòng Tuyển sinh & Công tác sinh viên",
        "short": "CTSV",
        "domain": "ctsv.chat.uel.edu.vn",
        "module": "cong_tac_sinh_vien",
        "module_name": "Công tác sinh viên",
    },
    {
        "dir": "phong-dao-tao",
        "id": "pdt",
        "name": "Phòng Đào tạo",
        "short": "PĐT",
        "domain": "pdt.chat.uel.edu.vn",
        "module": "dao_tao",
        "module_name": "Đào tạo",
    },
    {
        "dir": "phong-quan-tri-tai-san",
        "id": "qtts",
        "name": "Phòng Quản trị tài sản",
        "short": "QTTS",
        "domain": "qtts.chat.uel.edu.vn",
        "module": "quan_tri_tai_san",
        "module_name": "Quản trị tài sản",
    },
    {
        "dir": "vien-quoc-te",
        "id": "vqt",
        "name": "Viện Quốc tế",
        "short": "VQT",
        "domain": "vqt.chat.uel.edu.vn",
        "module": "vien_quoc_te",
        "module_name": "Viện Quốc tế",
    },
    {
        "dir": "phong-nhan-su",
        "id": "pns",
        "name": "Phòng Nhân sự",
        "short": "PNS",
        "domain": "pns.chat.uel.edu.vn",
        "module": "nhan_su",
        "module_name": "Nhân sự",
    },
    {
        "dir": "phong-khoa-hoc-cong-nghe",
        "id": "khcn",
        "name": "Phòng Khoa học công nghệ",
        "short": "KHCN",
        "domain": "khcn.chat.uel.edu.vn",
        "module": "khoa_hoc_cong_nghe",
        "module_name": "Khoa học công nghệ",
    },
    {
        "dir": "phong-bao-dam-chat-luong",
        "id": "dbcl",
        "name": "Phòng Bảo đảm chất lượng",
        "short": "ĐBCL",
        "domain": "dbcl.chat.uel.edu.vn",
        "module": "khao_khi",
        "module_name": "Mô-đun Khảo thí",
    },
]


def ignore(directory: str, names: list[str]) -> set[str]:
    return {n for n in names if n in SKIP or n == "_seed_rooms.py"}


def write_department_yaml(dest: Path, room: dict) -> None:
    text = f"""id: {room["id"]}
name: {room["name"]}
domain: {room["domain"]}
handoff_form_url: ""
admins: []
rate_limit:
  chats_per_minute: 10
  llm_tokens_per_day: 50000
modules:
  - code: {room["module"]}
    name: {room["module_name"]}
    profile: generic
"""
    (dest / "chatbot-api" / "configs" / "department.yaml").write_text(text, encoding="utf-8")


def write_department_js(dest: Path, room: dict) -> None:
    text = f"""/** Nhận diện giao diện. DEPARTMENT_ID runtime lấy từ backend / .env, không lấy file này. */
export const department = {{
  short: {room["short"]!r},
  name: {room["name"]!r},
  id: {room["id"]!r},
}}

export const navigation = {{
  chat: '/',
  login: '/dang-nhap',
  admin: '/quan-ly',
}}
"""
    (dest / "chatbot-web" / "src" / "config" / "department.js").write_text(text, encoding="utf-8")


def patch_compose_and_env(dest: Path, room: dict) -> None:
    compose = dest / "docker-compose.yml"
    text = compose.read_text(encoding="utf-8")
    if "labels:" not in text:
        text = text.replace(
            'ports:\n      - "8000:8000"\n',
            "labels:\n"
            f"      - traefik.http.routers.{room['id']}.rule=Host(`{room['domain']}`)\n"
            '    ports:\n      - "8000:8000"\n',
        )
        compose.write_text(text, encoding="utf-8")
    env = (dest / ".env.example").read_text(encoding="utf-8")
    env = env.replace("DEPARTMENT_ID=starter", f"DEPARTMENT_ID={room['id']}")
    (dest / ".env.example").write_text(env, encoding="utf-8")
    html = dest / "chatbot-web" / "index.html"
    html.write_text(
        html.read_text(encoding="utf-8").replace(
            "<title>Trợ lý UEL</title>",
            f"<title>Trợ lý {room['short']} | UEL</title>",
        ),
        encoding="utf-8",
    )


def main() -> None:
    for room in ROOMS:
        dest = ROOT / room["dir"]
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(STARTER, dest, ignore=ignore)
        write_department_yaml(dest, room)
        write_department_js(dest, room)
        patch_compose_and_env(dest, room)
        print("copied", dest.name)


if __name__ == "__main__":
    main()
