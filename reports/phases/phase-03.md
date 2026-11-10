# Báo cáo Phase 3 — Silver Layer và đồng bộ idempotent

## 1. Metadata

| Thuộc tính | Giá trị |
|---|---|
| Phase | 3 |
| Trạng thái | `ACCEPTED` |
| Ngày bắt đầu | 2026-11-10 |
| Ngày kết thúc | 2026-11-10 |
| Phạm vi | Phòng Bảo đảm chất lượng / Mô-đun Khảo khí |
| `department_id` | `bao_dam_chat_luong` |
| `module_code` | `khao_khi` |
| Người thực hiện | Lê Gia Văn / dự án UEL Innovation |
| Commit/Tag | Working tree Phase 3 (chưa commit) |

## 2. Mục tiêu

- Chốt ERD và tạo schema PostgreSQL (SQLAlchemy 2.0 + Alembic) cho Silver Layer.
- Upsert idempotent theo business key ổn định; không dùng STT làm khóa.
- Ghi `sync_runs` trước khi load; sync lỗi không để Silver nửa vời.
- Soft-delete record biến mất khỏi nguồn (`is_active=false`).
- Kế thừa contact record → module → department theo policy; unverified chỉ ở development/test.
- Dry-run không ghi PostgreSQL. Không sửa workbook nguồn.

## 3. Checklist hoàn thành

- [x] P3.01 — ERD (`docs/erd.md`).
- [x] P3.02 — SQLAlchemy models (`app/models/tables.py`).
- [x] P3.03 — Alembic `20261110_0001_silver_layer`.
- [x] P3.04–P3.12 — `departments`, `modules`, `routing_rules`, `faqs`, `documents`, `document_sections`, `procedures`, `dossier_items`, `procedure_steps`, `attachments`, `sync_runs`, `source_records`.
- [x] P3.13–P3.14 — Unicode NFC / khoảng trắng; tên chuẩn `Phòng Bảo đảm chất lượng` / `Khảo khí`.
- [x] P3.15 — Content hash trên payload đã chuẩn hóa.
- [x] P3.16 — Upsert theo business key.
- [x] P3.17 — Transaction: commit `SyncRun(started)` rồi load; exception → `failed`.
- [x] P3.18 — Soft-delete bằng `last_seen_sync_run_id`.
- [x] P3.19 — `resolve_contact` + inheritance.
- [x] P3.20 — Stale `started`/`loading_silver` đánh `failed`; retry = chạy lại `sync`.
- [x] P3.21 — Cùng input hai lần: lần 2 unchanged, không duplicate.
- [x] P3.22 — Integration tests PostgreSQL (`tests/integration/`).

## 4. Deliverables

| Deliverable | Đường dẫn | Trạng thái |
|---|---|---|
| ERD | `docs/erd.md` | Hoàn thành |
| ORM models | `app/models/tables.py` | Hoàn thành |
| Alembic | `alembic/versions/20261110_0001_silver_layer.py` | Hoàn thành |
| Silver writer | `app/repositories/silver.py` | Hoàn thành |
| Contact policy | `app/ingestion/contact.py` | Hoàn thành |
| Pipeline/CLI Silver | `app/ingestion/pipeline.py`, `app/cli.py` | Hoàn thành |
| Unit contact tests | `tests/unit/test_contact.py` | Hoàn thành |
| Integration tests | `tests/integration/test_silver_postgres.py` | Hoàn thành |

## 5. Kết quả kiểm tra

| Kiểm tra | Kỳ vọng | Kết quả | Evidence |
|---|---|---|---|
| `ruff check .` / `ruff format --check .` | Pass | Pass | 2026-11-10 |
| `mypy app tests` | Pass | Pass | 2026-11-10 |
| `pytest --cov=app` | Pass | 27 passed, coverage 88% | gồm marker `integration` |
| Mini release idempotent | Lần 2 không duplicate FAQ | Pass | `test_mini_release_is_idempotent` |
| Đổi một ô FAQ | Cùng `id`, đổi hash/answer; FAQ khác giữ nguyên | Pass | `test_one_cell_change_updates_only_that_faq` |
| Sync lỗi | `sync_runs.status=failed`, 0 FAQ | Pass | `test_failed_sync_is_recorded_and_leaves_no_partial_silver` |
| PoC counts trên `uel_rag_test` | 1/1/17/71/4 + 15/26 | Pass | `test_poc_counts_match_exit_gate` |
| Contact unverified | Inherit ở test/dev; UAT `allow_unverified=false` → null | Pass | `test_unverified_module_contact_inherited_only_in_development` |
| Live `uel_rag` lần 1 | 17/71/4, inserted 158, unchanged 1 | Pass | sync_run `c8eee812-…` |
| Live `uel_rag` lần 2 | inserted 0, updated 0, deactivated 0, unchanged 159 | Pass | sync_run `cf47e46d-…` |
| Source XLSX checksum | Không đổi | Pass | Manifest sau sync |

### 5.1. CLI sync trên `uel_rag` (2026-11-10)

Host: `$env:POSTGRES_HOST="localhost"`; `$env:MINIO_URL="http://localhost:9000"`.

Lần 1 (`c8eee812-d1eb-48c4-ad3e-430dabd5cb22`): `status=completed`, silver_inserted=158, silver_unchanged=1 (URL đính kèm trùng trên cùng document).

Lần 2 (`cf47e46d-91ef-444a-91ba-c06add3fafd6`): silver_inserted=0, silver_updated=0, silver_deactivated=0, silver_unchanged=159.

SQL sau lần 2:

| Bảng | Active count |
|---|---:|
| departments | 1 |
| modules | 1 |
| routing_rules | 17 |
| faqs | 71 |
| documents | 4 |
| document_sections (regulation) | 15 |
| document_sections (condition) | 26 |
| procedures | 3 |
| dossier_items | 4 |
| procedure_steps | 13 |

Dry-run vẫn `persist_silver=False` / `NullSilverWriter`: không ghi PostgreSQL.

## 6. Exit gate

| Điều kiện | Kết quả | Ghi chú |
|---|---|---|
| 1 department, 1 module PoC | Pass | `bao_dam_chat_luong` / `khao_khi` |
| 17 routing rules active | Pass | |
| 71 FAQ | Pass | |
| 4 documents + sections | Pass | 15 regulation + 26 condition; TL02–04: 4 dossier, 13 steps, 3 procedures |
| Chạy lại cùng input không duplicate | Pass | unchanged=159 |
| Đổi một ô chỉ cập nhật record liên quan | Pass | Integration test |
| Sync lỗi không để trạng thái nửa vời không ghi nhận | Pass | `failed` + rollback load |

## 7. Quyết định kỹ thuật (Phase 3)

| ID | Quyết định | Lý do |
|---|---|---|
| DEC-P3-01 | PostgreSQL Silver là nguồn chân lý; Qdrant rebuild ở Phase 4 | PLAN: không dual-write Gold từ Bronze |
| DEC-P3-02 | Upsert theo business key, không theo STT | STT đổi khi sắp xếp lại sheet |
| DEC-P3-03 | Commit `SyncRun(started)` rồi load; exception đánh `failed` | Audit luôn có, Silver không partial |
| DEC-P3-04 | Soft-delete `is_active=false` + `last_seen_sync_run_id` | Record biến mất khỏi nguồn vẫn truy vết |
| DEC-P3-05 | Unverified contact inherit chỉ development/test | DEC-09; UAT/prod cần `verified: true` |
| DEC-P3-06 | Attachment unique `(document_id, source_url)` | Cùng URL portal trên một document gộp một hàng |
| DEC-P3-07 | Retry = chạy lại `sync`; stale run đánh `failed` | Không resume giữa chừng |
| DEC-P3-08 | Alembic URL lấy từ `Settings.postgres_sync_url` | Host CLI: `POSTGRES_HOST=localhost` |
| DEC-P3-09 | Tên hiển thị khóa `Khảo khí`, không tự sửa thành “Khảo thí” | DEC-06 |

## 8. Blocker và ngoại lệ

| ID | Nội dung | Owner | Hạn xử lý | Ảnh hưởng |
|---|---|---|---|---|
| — | Không có blocker mới | — | — | — |

UAT gates Phase 0 (BLK-03–BLK-05) không chặn Phase 4. Contact YAML hiện `verified: false` — hợp lệ cho development, không đủ cho UAT.

## 9. Rủi ro chuyển Phase 4

- Gold/Qdrant phải đọc Silver active records, không parse lại XLSX.
- Content hash Silver là tín hiệu re-embed; Phase 4 không được embed bản `is_active=false` trừ khi policy yêu cầu xóa vector.
- Unique `(document_id, source_url)` làm URL dùng chung gộp một attachment — Gold citation cần dùng `document_id` + `source_url`.
- Sync từ máy host cần `POSTGRES_HOST=localhost` và `MINIO_URL=http://localhost:9000`; trong Compose dùng hostname dịch vụ.
- FAQ thiếu căn cứ (DATA-05) vẫn nằm trong Silver development; retrieval/eval phải gắn cờ này.

## 10. Kết luận

**Kết quả: `ACCEPTED`**

Phase 3 đã đưa dữ liệu PoC Khảo khí vào PostgreSQL đúng số lượng, upsert idempotent, ghi nhận sync thất bại, và giữ nguyên workbook nguồn. Phase 4 có thể bắt đầu: STAIR, embedding và Gold Layer trên Qdrant.
