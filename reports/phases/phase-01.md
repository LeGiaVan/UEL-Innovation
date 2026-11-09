# Báo cáo Phase 1 — Nền tảng repository và hạ tầng local

## 1. Metadata

| Thuộc tính | Giá trị |
|---|---|
| Phase | 1 |
| Trạng thái | `ACCEPTED` |
| Ngày bắt đầu | 2026-11-09 |
| Ngày kết thúc | 2026-11-09 |
| Phạm vi | Phòng Bảo đảm chất lượng / Mô-đun Khảo khí |
| `department_id` | `bao_dam_chat_luong` |
| `module_code` | `khao_khi` |
| Người thực hiện | Lê Gia Văn / dự án UEL Innovation |
| Commit/Tag | `e9ea43c` |

## 2. Mục tiêu

- Khởi tạo repository Python 3.12 với chuẩn chất lượng (lint, type check, test).
- Cấu hình application qua Pydantic Settings và department config YAML.
- Dựng stack Docker Compose local: PostgreSQL, Qdrant, MinIO, FastAPI API shell.
- Cung cấp health liveness/readiness, structured logging và request ID.
- Đạt exit gate Phase 1 trước khi bắt đầu Bronze ingestion (Phase 2).

## 3. Checklist hoàn thành

- [x] P1.01 — Khởi tạo package Python 3.12 (`pyproject.toml`, `requires-python >=3.12`).
- [x] P1.02 — Tạo cấu trúc `app/`, `tests/`, `configs/`, `docs/`.
- [x] P1.03 — Cấu hình dependency management (`pip install -e ".[dev]"`).
- [x] P1.04 — Cấu hình formatter, linter và type checker (ruff, mypy).
- [x] P1.05 — Tạo `.gitignore` và `.env.example`.
- [x] P1.06 — Tạo configuration model bằng Pydantic Settings (`app/core/config.py`).
- [x] P1.07 — Tạo `configs/departments.yaml`.
- [x] P1.08 — Cấu hình `department_id=bao_dam_chat_luong`, `module_code=khao_khi`.
- [x] P1.09 — Tạo Dockerfile cho API.
- [x] P1.10 — Tạo Docker Compose cho PostgreSQL, Qdrant, MinIO và API.
- [x] P1.11 — Tạo named volumes và internal network (`backend`).
- [x] P1.12 — Tạo health checks cho từng service.
- [x] P1.13 — Thiết lập structured logging và request ID (`structlog`, middleware).
- [x] P1.14 — Thiết lập Pytest và smoke test (`tests/smoke/test_health.py`, `tests/unit/test_config.py`).
- [x] P1.15 — Kiểm tra secret không xuất hiện trong Git (chỉ placeholder trong `.env.example`; `.env` gitignored).

## 4. Deliverables

| Deliverable | Đường dẫn | Trạng thái |
|---|---|---|
| Python package & tooling | `pyproject.toml` | Hoàn thành |
| Application core | `app/` | Hoàn thành |
| Health endpoints | `app/api/routes/health.py` | Hoàn thành |
| Department config | `configs/departments.yaml` | Hoàn thành |
| Compose stack | `docker-compose.yml` | Hoàn thành |
| API image | `Dockerfile` | Hoàn thành |
| MinIO PoC image | `infra/minio/Dockerfile` | Hoàn thành |
| Env template | `.env.example` | Hoàn thành |
| Tests | `tests/` | Hoàn thành |
| Hướng dẫn chạy | `README.md` §16 | Hoàn thành |

## 5. Kết quả kiểm tra

| Kiểm tra | Kỳ vọng | Kết quả | Evidence |
|---|---|---|---|
| `ruff check .` | Pass | Pass | 2026-11-09, local |
| `ruff format --check .` | Pass | Pass | 27 files formatted |
| `mypy app tests` | Pass | Pass | 15 source files |
| `pytest` | Pass | 5 passed | ~1.6s |
| Coverage `app` | Có baseline | 88% | smoke + unit |
| `Settings` thiếu biến bắt buộc | `ValidationError` | Pass | `tests/unit/test_config.py` |
| `docker compose up -d --build` | Khởi động thành công | Pass | 2026-11-09 |
| `docker compose ps` | 4/4 healthy | Pass | postgres, qdrant, minio, api |
| `GET /health/live` | 200, `ok` | Pass | `curl localhost:8000/health/live` |
| `GET /health/ready` | 200, dependencies `ok` | Pass | Xem §5.1 |
| Secret trong Git | Không có secret thật | Pass | `.env` gitignored; example dùng placeholder |

### 5.1. Readiness (sau khởi tạo volume đồng bộ mật khẩu)

```json
{
  "status": "ready",
  "dependencies": {
    "postgres": "ok",
    "qdrant": "ok",
    "minio": "ok"
  }
}
```

**Ghi chú vận hành:** Nếu đổi `POSTGRES_PASSWORD` trong `.env` mà giữ volume `postgres_data` cũ, API readiness báo `postgres: error`. Khắc phục PoC: `docker compose down -v` rồi `up` lại, hoặc khớp mật khẩu với cluster đã khởi tạo.

## 6. Exit gate

| Điều kiện | Kết quả | Ghi chú |
|---|---|---|
| `docker compose up` khởi động thành công | Pass | Windows + Docker Desktop |
| PostgreSQL, Qdrant, MinIO healthy | Pass | Compose healthcheck |
| Readiness phản ánh dependency | Pass | Sau reset volume |
| Cấu hình thiếu biến bắt buộc fail-fast | Pass | Unit test |
| Không có secret thật trong repository | Pass | |
| Smoke test chạy thành công | Pass | 5/5 |

## 7. Quyết định kỹ thuật (Phase 1)

| ID | Quyết định | Lý do |
|---|---|---|
| DEC-P1-01 | MinIO image build từ binary release đã pin checksum | Không có public image ổn định tại thời điểm PoC; chỉ dùng development |
| DEC-P1-02 | Readiness kiểm tra Postgres bằng `SELECT 1` qua async SQLAlchemy | Chuẩn bị Phase 3; không migration ở Phase 1 |
| DEC-P1-03 | API shell chưa có `/v1/chat` | Thuộc Phase 7; Phase 1 chỉ health + config |

## 8. Blocker và ngoại lệ

| ID | Nội tung | Owner | Hạn xử lý | Ảnh hưởng |
|---|---|---|---|---|
| — | Không có blocker mới | — | — | — |

Các UAT release gate từ Phase 0 (BLK-03–BLK-05) không ảnh hưởng Phase 1.

## 9. Rủi ro chuyển Phase 2

- Parser Bronze phải tuân schema fingerprint; không được giả định template gốc.
- MinIO image tự build cần đánh giá lại trước production/Ubuntu deploy.
- Mật khẩu Postgres và volume: cần ghi rõ trong runbook khi rotate secret.
- `app/services/health.py` chưa được integration test trong container (chỉ unit/smoke ASGI).

## 10. Kết luận

**Kết quả: `ACCEPTED`**

Phase 1 đã cung cấp nền tảng repository, cấu hình và hạ tầng local đủ điều kiện bắt đầu Phase 2 — Bronze ingestion và validation.
