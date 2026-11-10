# Báo cáo Phase 2 — Bronze ingestion và validation

## 1. Metadata

| Thuộc tính | Giá trị |
|---|---|
| Phase | 2 |
| Trạng thái | `ACCEPTED` |
| Ngày bắt đầu | 2026-11-10 |
| Ngày kết thúc | 2026-11-10 |
| Phạm vi | Phòng Bảo đảm chất lượng / Mô-đun Khảo khí |
| `department_id` | `bao_dam_chat_luong` |
| `module_code` | `khao_khi` |
| Người thực hiện | Lê Gia Văn / dự án UEL Innovation |
| Commit/Tag | Working tree Phase 2 (chưa commit) |

## 2. Mục tiêu

- Đọc ba workbook PoC bằng XLSX adapter, nhận diện schema bằng fingerprint chứ không dựa vào tên file.
- Validate raw records theo policy Phase 0 (ERROR/WARNING/INFO).
- Xuất báo cáo validation JSON và Markdown.
- Lưu snapshot Bronze (checksum + MinIO) khi không `--dry-run`.
- Không ghi PostgreSQL hoặc Qdrant; không sửa workbook nguồn.

## 3. Checklist hoàn thành

- [x] P2.01 — `SourceAdapter` (`app/ingestion/adapter.py`).
- [x] P2.02 — XLSX adapter (`app/ingestion/xlsx_adapter.py`).
- [x] P2.03 — Bỏ sheet hướng dẫn/ẩn (`Hướng dẫn`, `MẪU`, `_DS`); chỉ đọc `Tài liệu N`.
- [x] P2.04 — Nhận diện workbook bằng schema fingerprint.
- [x] P2.05 — Đọc module metadata và routing rows.
- [x] P2.06 — Đọc 71 FAQ.
- [x] P2.07 — Đọc TL01–TL04 theo schema thực tế.
- [x] P2.08 — Source location: file, sheet, row, column.
- [x] P2.09 — File SHA-256 và schema SHA-256.
- [x] P2.10 — Upload Bronze qua `MinioBronzeStore` (unit test bằng `NullBronzeStore`).
- [x] P2.11 — Pydantic raw models (`app/ingestion/models.py`).
- [x] P2.12–P2.17 — Validation required fields, FAQ unique, routing enum, URL/email, “Chưa xác định”, severity.
- [x] P2.18 — Report JSON + Markdown.
- [x] P2.19 — `python -m app.cli sync --dry-run`.
- [x] P2.20 — Unit tests fixture tối thiểu + test PoC thật.

## 4. Deliverables

| Deliverable | Đường dẫn | Trạng thái |
|---|---|---|
| Ingestion package | `app/ingestion/` | Hoàn thành |
| CLI | `app/cli.py` | Hoàn thành |
| XLSX fixture builder | `tests/helpers/xlsx_builder.py` | Hoàn thành |
| Unit/PoC tests | `tests/unit/test_*.py` | Hoàn thành |
| Validation output (generated) | `reports/validation/` (gitignored) | Hoàn thành |

## 5. Kết quả kiểm tra

| Kiểm tra | Kỳ vọng | Kết quả | Evidence |
|---|---|---|---|
| `ruff check .` / `ruff format --check .` | Pass | Pass | 2026-11-10 |
| `mypy app tests` | Pass | Pass | 38 source files |
| `pytest --cov=app` | Pass | 20 passed, coverage 86% | 2026-11-10 |
| Parser counts | 17/71/4 + 15/26/4/13 | Pass | `test_poc_xlsx_matches_phase0_exit_gate_counts` |
| Dry-run CLI | 0 ERROR, không ghi PG/Qdrant | Pass | `python -m app.cli sync --dry-run` |
| DATA-01…DATA-10 | Có trong report | Pass | `validation.md` policy findings |
| FAQ thiếu căn cứ | 59 WARNING | Pass | 59 `DATA-05` |
| Lệ phí chưa xác định | 3 WARNING | Pass | TL02–TL04 `DATA-07` |
| Source XLSX checksum | Không đổi | Pass | So khớp manifest sau dry-run |
| Identify by fingerprint | Đổi tên file vẫn nhận FAQ | Pass | `test_identify_workbook_by_fingerprint_not_filename` |
| Duplicate FAQ / invalid scope | ERROR | Pass | mini fixtures |
| Google Sheets | Chưa triển khai, exit 4 | Pass | CLI `--source google-sheets` |

### 5.1. Dry-run PoC (2026-11-10)

```text
release: bdcl-khao-khi-2026-11-09-002
status: validated
dry_run: True
routing_rules: 17
faqs: 71
documents: 4
errors: 0
warnings: 62
infos: 1
publish_allowed: True
```

62 WARNING = 59 FAQ thiếu văn bản căn cứ + 3 lệ phí “Chưa xác định”. Không có ERROR nên `publish_allowed=true` cho development.

## 6. Exit gate

| Điều kiện | Kết quả | Ghi chú |
|---|---|---|
| Parser đọc đúng 17 routing rules | Pass | |
| Parser đọc đúng 71 FAQ | Pass | |
| Parser đọc đủ TL01–TL04 | Pass | Kèm 15/26/4/13 |
| Mọi record-level issue có source location | Pass | |
| Dry-run không ghi PostgreSQL/Qdrant | Pass | Phase 2 không có writer Silver/Gold |
| Report phản ánh DATA-01 đến DATA-10 | Pass | |
| Dữ liệu nguồn không bị thay đổi | Pass | |

## 7. Quyết định kỹ thuật (Phase 2)

| ID | Quyết định | Lý do |
|---|---|---|
| DEC-P2-01 | Nhận diện workbook bằng schema fingerprint trước, tên file chỉ là nhãn | P2.04; hỗ trợ đổi tên file khi checksum/schema khớp |
| DEC-P2-02 | Dry-run không upload MinIO | Tránh ghi phụ thuộc khi chỉ kiểm tra parser |
| DEC-P2-03 | Checksum/schema mismatch chặn extract | Policy Phase 0: dừng sync, yêu cầu release mới |
| DEC-P2-04 | Google Sheets adapter chỉ skeleton | DR-010: XLSX trước |
| DEC-P2-05 | Validation ERROR chặn publish; WARNING vẫn `validated` ở development | DATA-05/DATA-07 được phép trong `approved_for_dev` |

## 8. Blocker và ngoại lệ

| ID | Nội dung | Owner | Hạn xử lý | Ảnh hưởng |
|---|---|---|---|---|
| — | Không có blocker mới | — | — | — |

UAT gates Phase 0 (BLK-03–BLK-05) không chặn Phase 3.

## 9. Rủi ro chuyển Phase 3

- Silver upsert phải dùng đúng business key đã tính ở Bronze (`question_code`, `document_code`, routing `source_key`).
- COUNT_MISMATCH là ERROR so với manifest; đổi dữ liệu nguồn bắt buộc tạo release mới.
- MinIO upload từ máy host cần `MINIO_URL=http://localhost:9000` (Compose dùng hostname `minio`).
- Contact inheritance mới ghi nhận INFO; việc ghi Silver contact xảy ra ở Phase 3.

## 10. Kết luận

**Kết quả: `ACCEPTED`**

Phase 2 đã đọc và validate đủ dữ liệu PoC Khảo khí, xuất báo cáo theo ô nguồn, và giữ nguyên workbook. Phase 3 có thể bắt đầu: Silver Layer PostgreSQL và đồng bộ idempotent.
