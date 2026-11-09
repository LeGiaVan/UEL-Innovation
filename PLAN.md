# Kế hoạch triển khai UEL RAG Chatbot PoC

## 1. Thông tin kế hoạch

| Thuộc tính | Giá trị |
|---|---|
| Phạm vi | PoC |
| Phòng ban | Phòng Đảm Bảo Chất Lượng |
| `department_id` | `dam_bao_chat_luong` |
| Thời lượng | 8 tuần |
| Nhân sự | 1 người |
| Hạ tầng | Ubuntu Server, Docker Compose, CPU-only |
| Kênh | FastAPI và web chat tối thiểu |
| Xác thực | API key qua FastAPI dependency |
| LLM | Cloud, provider-agnostic |
| Embedding | Local trên CPU |
| Đồng bộ | On-demand |
| Nguồn dữ liệu | XLSX khi phát triển, Google Sheets khi tích hợp |

## 2. Mục tiêu nghiệm thu

PoC được coi là hoàn thành khi:

1. Ba biểu mẫu được đọc và validation tự động.
2. Dữ liệu hợp lệ được lưu vào PostgreSQL.
3. Tài liệu được serialize theo STAIR và index vào Qdrant.
4. File đính kèm được quản lý qua MinIO.
5. Pipeline chạy lại không tạo dữ liệu trùng.
6. Routing, FAQ và RAG hoạt động end-to-end.
7. Mọi câu trả lời RAG đều có citation.
8. Hệ thống từ chối trả lời khi không đủ bằng chứng.
9. API được bảo vệ bằng API key.
10. Web chat có thể gửi câu hỏi và hiển thị nguồn.
11. Bộ đánh giá đạt KPI đã thống nhất.
12. Docker Compose khởi chạy được trên Ubuntu Server.
13. Có hướng dẫn vận hành, đồng bộ, backup và xử lý sự cố.

## 3. Giả định

- Chuyên viên Phòng Đảm Bảo Chất Lượng cung cấp dữ liệu thử nghiệm.
- Dữ liệu không chứa thông tin cá nhân nhạy cảm.
- Tài liệu dùng cho PoC đã được xác nhận nội dung.
- Máy chủ có đủ RAM cho PostgreSQL, Qdrant, MinIO và embedding model.
- Có quyền truy cập một cloud LLM được UEL chấp thuận.
- Có credential Google Sheets trước giai đoạn tích hợp.
- PoC không yêu cầu SSO.
- Web chat chỉ phục vụ demo/UAT, không phải portal production.
- Một người thực hiện nên mọi yêu cầu mở rộng phải được đưa vào backlog sau PoC.

## 4. Các quyết định kiến trúc

### ADR-001 — Một tenant cố định trong PoC

`department_id` được lấy từ cấu hình server, không lấy từ request.

Lý do:

- Giảm nguy cơ giả mạo tenant.
- Phù hợp phạm vi một phòng ban.
- Vẫn giữ trường `department_id` trong mọi bảng và payload để chuẩn bị mở rộng.

### ADR-002 — API key qua dependency injection

FastAPI `Depends` xác minh `X-API-Key` và tạo request context.

Không xây:

- User database.
- Login/logout.
- Refresh token.
- Phân quyền theo người dùng.
- SSO.

### ADR-003 — LLM cloud, embedding local

- LLM cloud giảm yêu cầu GPU.
- Embedding local giúp kiểm soát chi phí và dữ liệu index.
- Cả hai được bao bọc bởi interface để có thể thay provider/model.

### ADR-004 — PostgreSQL là nguồn chân lý

Qdrant chỉ là index có thể tái tạo. Khi dữ liệu không đồng nhất:

- PostgreSQL được xem là nguồn đúng.
- Qdrant được rebuild từ Silver Layer.

### ADR-005 — Trả lời có bằng chứng hoặc không trả lời

Không cho phép LLM sử dụng kiến thức chung để bổ sung quy định UEL.

## 5. Data contract cần khóa trong Tuần 1

### Biểu mẫu 01

Cần xác định:

- Khóa ổn định của routing rule.
- Giá trị hợp lệ của loại phạm vi.
- Trạng thái của từng dòng.
- Trường bắt buộc cho human handoff.
- Cách xử lý dòng trống, dòng trùng và URL lỗi.

### Biểu mẫu 02

Cần xác định:

- `MÃ CÂU HỎI` phải duy nhất.
- FAQ nào đang hoạt động.
- Đối tượng áp dụng.
- Ngày hiệu lực.
- Quy tắc chuẩn hóa câu hỏi.
- Có hỗ trợ nhiều cách hỏi cho cùng FAQ hay không.

### Biểu mẫu 03

Cần xác định:

- Mỗi `TLxx` là một tài liệu độc lập.
- Trạng thái `Nháp`, `Đã duyệt`, `Ngưng dùng`.
- Quy tắc hiệu lực ngày.
- Định dạng URL.
- Cách ánh xạ đối tượng áp dụng.
- Kích thước tối đa của một mục.
- Cách xử lý file đính kèm không tải được.

## 6. Mô hình dữ liệu đề xuất

### PostgreSQL

#### `departments`

- `id`
- `code`
- `name`
- `audience`
- `is_active`
- `created_at`
- `updated_at`

#### `modules`

- `id`
- `department_id`
- `source_id`
- `name`
- `source_created_at`
- `source_updated_at`
- `content_hash`
- `sync_run_id`

#### `routing_rules`

- `id`
- `department_id`
- `module_id`
- `source_key`
- `scope_type`
- `topic`
- `bot_behavior`
- `support_contact`
- `contact_information`
- `online_channel`
- `status`
- `content_hash`
- `sync_run_id`

#### `faqs`

- `id`
- `department_id`
- `question_code`
- `category`
- `subcategory`
- `question`
- `normalized_question`
- `answer`
- `legal_basis`
- `applicable_to`
- `support_contact`
- `contact_information`
- `online_channel`
- `effective_from`
- `effective_to`
- `status`
- `content_hash`
- `sync_run_id`

#### `documents`

- `id`
- `department_id`
- `document_code`
- `title`
- `document_type`
- `summary`
- `aliases`
- `applicable_to`
- `program_scope`
- `excluded_audience`
- `legal_basis`
- `support_contact`
- `effective_from`
- `effective_to`
- `status`
- `source_version`
- `content_hash`
- `sync_run_id`

#### `document_sections`

- `id`
- `document_id`
- `section_type`
- `section_order`
- `heading`
- `content`
- `serialized_markdown`
- `content_hash`

#### `attachments`

- `id`
- `document_id`
- `form_code`
- `file_name`
- `source_url`
- `object_key`
- `mime_type`
- `checksum`
- `status`

#### `sync_runs`

- `id`
- `department_id`
- `source_type`
- `started_at`
- `completed_at`
- `status`
- `source_checksum`
- `inserted_count`
- `updated_count`
- `deactivated_count`
- `error_count`
- `report_object_key`

#### `source_records`

- `id`
- `sync_run_id`
- `workbook`
- `sheet`
- `row_number`
- `source_key`
- `raw_payload`
- `validation_status`
- `validation_errors`

### Qdrant payload

```json
{
  "department_id": "dam_bao_chat_luong",
  "document_id": "uuid",
  "document_code": "TL01",
  "section_id": "uuid",
  "section_type": "regulation",
  "title": "...",
  "applicable_to": ["..."],
  "program_scope": ["..."],
  "status": "approved",
  "effective_from": "2026-01-01",
  "effective_to": null,
  "source_version": "...",
  "content_hash": "...",
  "citation_url": "..."
}
```

## 7. Chiến lược đồng bộ

### Giai đoạn 1 — Extract

- Đọc XLSX hoặc Google Sheets.
- Lưu snapshot raw vào MinIO.
- Ghi checksum.
- Gắn workbook, sheet, dòng và cột cho từng giá trị.
- Không chỉnh sửa dữ liệu nguồn.

### Giai đoạn 2 — Validate

Phân loại lỗi:

- `ERROR`: không được publish.
- `WARNING`: được publish nhưng phải xuất báo cáo.
- `INFO`: ghi chú chuẩn hóa.

Ví dụ `ERROR`:

- Trùng mã câu hỏi.
- Tài liệu không có tên.
- Trạng thái không hợp lệ.
- Ngày hiệu lực sai định dạng.
- `effective_to < effective_from`.
- Tài liệu đã duyệt nhưng không có nội dung.
- URL bắt buộc không hợp lệ.

### Giai đoạn 3 — Transform và Load Silver

- Chuẩn hóa Unicode NFC.
- Chuẩn hóa khoảng trắng.
- Chuẩn hóa enum.
- Tạo khóa nội bộ.
- Tính content hash.
- Upsert bằng khóa nghiệp vụ.
- Soft-delete dữ liệu không còn hoạt động.
- Thực hiện trong transaction.

### Giai đoạn 4 — Serialize và Index Gold

- Chỉ lấy tài liệu đã duyệt và còn hiệu lực.
- Tạo STAIR Markdown.
- Chunk theo ranh giới ngữ nghĩa.
- Tạo embedding.
- Upsert Qdrant theo ID ổn định.
- Xóa hoặc vô hiệu vector của tài liệu ngưng dùng.
- Không re-embed nếu content hash không thay đổi.

### Giai đoạn 5 — Publish

Chỉ đánh dấu sync thành công khi:

- PostgreSQL commit thành công.
- Qdrant upsert thành công.
- Báo cáo được lưu.
- Không có lỗi nghiêm trọng.

Nếu Qdrant thất bại sau khi PostgreSQL commit, sync được đánh dấu `partial_failed` và phải có lệnh rebuild index.

## 8. LangGraph workflow

### State dự kiến

- `request_id`
- `department_id`
- `message`
- `normalized_message`
- `conversation_context`
- `routing_result`
- `faq_result`
- `extracted_metadata`
- `retrieved_chunks`
- `evidence_score`
- `answer`
- `citations`
- `support_contact`
- `status`
- `errors`

### Nodes

1. `normalize_input`
2. `routing_check`
3. `faq_match`
4. `metadata_extract`
5. `retrieve`
6. `evidence_gate`
7. `generate`
8. `citation_verify`
9. `format_response`
10. `handoff`
11. `error_handler`

### Quy tắc quan trọng

- Ngoài phạm vi thì không gọi retrieval hoặc LLM.
- FAQ phù hợp thì không gọi generation.
- Metadata từ LLM không được bỏ qua tenant filter.
- Tất cả filter bảo mật phải được xây ở server.
- Không đủ bằng chứng thì không generation.
- Citation không hợp lệ thì không trả câu trả lời như một kết luận chắc chắn.

## 9. Kế hoạch 8 tuần

### Tuần 1 — Discovery và khóa data contract

#### Mục tiêu

Loại bỏ các điểm mơ hồ trước khi viết pipeline.

#### Công việc

- Xác nhận phạm vi PoC.
- Thu thập dữ liệu mẫu của Phòng Đảm Bảo Chất Lượng.
- Kiểm kê ba workbook.
- Liệt kê tất cả sheet, cột, enum, validation và công thức.
- Xác định trường bắt buộc.
- Xác định khóa nghiệp vụ.
- Xử lý khoảng trống về status và effective date.
- Xác định quy tắc phê duyệt dữ liệu.
- Thiết kế data mapping Bronze → Silver → Gold.
- Chọn hai embedding model để benchmark.
- Xác nhận cloud LLM và chính sách dữ liệu.
- Viết architecture decision records.
- Tạo bộ 20–30 câu hỏi “golden questions” ban đầu.

#### Đầu ra

- Data dictionary.
- Mapping specification.
- Validation rules.
- ADR.
- Kiến trúc logical.
- Danh sách rủi ro.
- Bộ câu hỏi đánh giá ban đầu.

#### Tiêu chí hoàn thành

- Không còn cột nào chưa có quy tắc ánh xạ.
- Mỗi thực thể có khóa ổn định.
- Chuyên viên xác nhận dữ liệu nào được xem là đã duyệt.
- Cloud provider được phép sử dụng.

### Tuần 2 — Project foundation và hạ tầng

#### Công việc

- Khởi tạo cấu trúc Python.
- Thiết lập formatter, linter và type checking.
- Tạo Dockerfile.
- Tạo Docker Compose.
- Cấu hình PostgreSQL.
- Cấu hình Qdrant.
- Cấu hình MinIO.
- Tạo `.env.example`.
- Xây configuration loader.
- Xây `departments.yaml`.
- Thiết kế SQLAlchemy models.
- Tạo Alembic migration đầu tiên.
- Xây health check.
- Thiết lập structured logging.
- Tạo test fixture cho phòng ban giả để test isolation.

#### Đầu ra

- Stack hạ tầng khởi động được.
- Schema PostgreSQL ban đầu.
- Qdrant collection initializer.
- MinIO bucket initializer.
- Health endpoints.
- Unit test foundation.

#### Tiêu chí hoàn thành

- `docker compose up` thành công.
- Migration chạy lại được.
- Ready check phát hiện đúng service bị lỗi.
- Secret không xuất hiện trong log.

### Tuần 3 — Extract, validation và Bronze/Silver

#### Công việc

- Xây extractor interface.
- Xây XLSX extractor.
- Xây Google Sheets extractor skeleton.
- Đọc biểu mẫu mô-đun.
- Đọc FAQ.
- Đọc từng sheet `TLxx`.
- Lưu raw snapshot vào MinIO.
- Xây Pydantic models.
- Xây validation report.
- Chuẩn hóa enum, ngày, URL và Unicode.
- Xây repository layer.
- Upsert PostgreSQL.
- Ghi `sync_runs` và `source_records`.
- Viết unit test cho dữ liệu hợp lệ và không hợp lệ.

#### Đầu ra

- Lệnh `sync --dry-run`.
- Báo cáo lỗi theo ô dữ liệu.
- Dữ liệu sạch trong PostgreSQL.
- Snapshot dữ liệu nguồn.

#### Tiêu chí hoàn thành

- Dữ liệu sai không được publish.
- Chạy lại cùng input không tạo bản ghi trùng.
- Báo cáo xác định đúng workbook, sheet, dòng và cột.
- Có test cho duplicate, invalid date và invalid status.

### Tuần 4 — STAIR, embedding và Qdrant

#### Công việc

- Xây serializer cho từng loại section.
- Thêm metadata chung vào mỗi chunk.
- Xây chunking theo cấu trúc.
- Benchmark embedding model trên CPU.
- Đánh giá chất lượng với câu hỏi tiếng Việt.
- Đo thời gian embedding và dung lượng vector.
- Xây embedding adapter.
- Xây Qdrant indexer.
- Xây hard filter theo department, status, audience và hiệu lực.
- Xây index rebuild command.
- Xây soft-delete.
- Chỉ re-embed nội dung thay đổi.
- Viết retrieval test.

#### Đầu ra

- STAIR Markdown.
- Qdrant collection có payload.
- Báo cáo benchmark embedding.
- Rebuild và incremental indexing command.

#### Tiêu chí hoàn thành

- Không có chunk mất tên chủ đề hoặc đối tượng.
- Tài liệu `Nháp` và `Ngưng dùng` không được truy xuất.
- Filter tenant được áp dụng trong mọi truy vấn.
- Recall@5 sơ bộ đạt ít nhất 80% trước tối ưu.

### Tuần 5 — LangGraph RAG agent

#### Công việc

- Xây input normalization.
- Xây semantic/rule router.
- Xây FAQ normalized matching.
- Xây metadata extractor.
- Xây retrieval fusion.
- Xây evidence scoring.
- Xây prompt tiếng Việt.
- Xây cloud LLM adapter.
- Xây generation node.
- Xây citation verifier.
- Xây abstention/handoff.
- Xử lý timeout, retry và provider error.
- Viết graph integration tests.

#### Đầu ra

- Agent chạy end-to-end từ câu hỏi tới câu trả lời.
- Câu trả lời có nguồn.
- Có trạng thái out-of-scope và insufficient-evidence.
- Provider có thể đổi bằng cấu hình.

#### Tiêu chí hoàn thành

- FAQ không gọi LLM.
- Ngoài phạm vi không gọi LLM.
- Không có câu trả lời RAG thiếu citation.
- Provider timeout không làm API treo vô hạn.
- LLM không thể thay đổi hard filter.

### Tuần 6 — FastAPI, API key và web chat

#### Công việc

- Xây request/response schema.
- Xây API key dependency.
- Dùng constant-time comparison.
- Inject tenant context cố định.
- Xây `/v1/chat`.
- Xây health endpoints.
- Chuẩn hóa exception.
- Thêm request ID.
- Thêm timeout và request-size limit.
- Thiết lập CORS cụ thể.
- Xây web chat tối thiểu.
- Hiển thị loading, lỗi, trạng thái handoff và citation.
- Viết API integration tests.
- Viết E2E smoke test.

#### Đầu ra

- REST API.
- Web chat.
- OpenAPI documentation.
- Authentication tests.

#### Tiêu chí hoàn thành

- Thiếu hoặc sai API key trả 401.
- Client không thể thay đổi `department_id`.
- Citation mở đúng nguồn.
- UI không render HTML không tin cậy từ LLM.
- API error không làm lộ stack trace hoặc secret.

### Tuần 7 — Đánh giá, bảo mật và hiệu năng

#### Công việc

- Mở rộng bộ đánh giá lên ít nhất 120 câu.
- Gắn expected route, expected source và expected answer facts.
- Chia tập calibration và test.
- Đo Recall@K.
- Đo groundedness và citation validity.
- Đo abstention.
- Kiểm thử prompt injection.
- Kiểm thử dữ liệu tenant giả.
- Kiểm thử tài liệu hết hiệu lực.
- Kiểm thử input dài và input rỗng.
- Load test 10 người dùng đồng thời.
- Tối ưu index, connection pool và cache FAQ.
- Điều chỉnh threshold chỉ trên calibration set.
- Chạy regression trên test set.

#### Cấu trúc bộ đánh giá tối thiểu

| Nhóm | Số câu tối thiểu |
|---|---:|
| FAQ | 30 |
| Tài liệu nghiệp vụ | 40 |
| Câu hỏi cần metadata | 15 |
| Ngoài phạm vi | 15 |
| Thiếu bằng chứng | 10 |
| Prompt injection/adversarial | 10 |
| Tổng | 120 |

#### Tiêu chí hoàn thành

- Tenant leakage bằng 0.
- Citation validity ≥ 95%.
- Groundedness ≥ 90%.
- Correct abstention ≥ 95%.
- Recall@5 ≥ 90%.
- Error rate load test < 1%.
- Không còn lỗi P0 hoặc P1.

### Tuần 8 — UAT, triển khai và bàn giao

#### Công việc

- Deploy lên Ubuntu Server.
- Cấu hình volume và network.
- Cấu hình HTTPS/reverse proxy nếu môi trường cho phép.
- Chạy migration.
- Đồng bộ dữ liệu đã duyệt.
- Chạy smoke test production-like.
- Tổ chức UAT với chuyên viên.
- Sửa lỗi thuộc phạm vi PoC.
- Viết runbook.
- Viết hướng dẫn nhập liệu.
- Viết hướng dẫn sync.
- Viết hướng dẫn backup/restore.
- Viết troubleshooting.
- Chuẩn bị demo và báo cáo KPI.
- Lập backlog sau PoC.

#### Đầu ra

- PoC triển khai được.
- UAT report.
- Evaluation report.
- Runbook.
- Data-entry guide.
- Backup/restore guide.
- Danh sách hạn chế và đề xuất mở rộng.

#### Tiêu chí hoàn thành

- UAT được xác nhận.
- Có thể dựng lại hệ thống từ repository và backup.
- Một lần sync mẫu hoàn thành không cần sửa trực tiếp database.
- Không có lỗi P0/P1.
- Các hạn chế PoC được ghi rõ.

## 10. Kế hoạch kiểm thử

### Unit tests

- Text normalization.
- Date parsing.
- Enum mapping.
- FAQ matching.
- Content hashing.
- STAIR serialization.
- Chunking.
- Evidence score.
- API key verification.

### Integration tests

- PostgreSQL repository.
- Alembic migration.
- MinIO upload/download.
- Qdrant upsert/filter/search.
- XLSX extractor.
- Google Sheets adapter.
- Cloud LLM adapter bằng mock.

### End-to-end tests

- FAQ.
- RAG thành công.
- Ngoài phạm vi.
- Không đủ bằng chứng.
- Tài liệu ngưng dùng.
- Tài liệu hết hiệu lực.
- API key sai.
- Provider timeout.
- Sync rồi truy vấn dữ liệu mới.

### Security tests

- Giả mạo `department_id`.
- Prompt injection.
- Citation URL độc hại.
- XSS từ nội dung LLM.
- API key trong query string.
- Secret leakage trong log.
- File path traversal.
- Tài liệu tenant giả xuất hiện trong retrieval.

## 11. KPI đề xuất

| KPI | Baseline | Mục tiêu PoC |
|---|---:|---:|
| Recall@5 | Đo Tuần 4 | ≥ 90% |
| MRR | Đo Tuần 4 | ≥ 0,80 |
| Answer correctness | Đo Tuần 5 | ≥ 85% |
| Groundedness | Đo Tuần 5 | ≥ 90% |
| Citation validity | Đo Tuần 5 | ≥ 95% |
| Correct abstention | Đo Tuần 5 | ≥ 95% |
| Tenant leakage | 0 | 0 |
| FAQ match | Đo Tuần 5 | ≥ 98% |
| Sync idempotency | — | 100% |
| Unreported sync errors | — | 0 |
| FAQ p95 | — | ≤ 1 giây |
| RAG p95 | — | ≤ 8 giây |
| API error ở 10 VU | — | < 1% |

Nếu không đạt KPI, báo cáo phải chỉ rõ nguyên nhân thuộc:

- Chất lượng dữ liệu.
- Retrieval.
- Metadata extraction.
- Generation.
- Provider latency.
- Hạ tầng.

## 12. Definition of Done

Một task chỉ hoàn thành khi:

- Code đã được format và lint.
- Type check không có lỗi nghiêm trọng.
- Có test phù hợp.
- Test liên quan chạy thành công.
- Không chứa secret.
- Có logging và error handling.
- Có tài liệu cấu hình nếu thêm biến môi trường.
- Migration có đường nâng cấp rõ ràng.
- Thay đổi retrieval có regression evaluation.
- Thay đổi data contract được cập nhật trong tài liệu.

## 13. Rủi ro

| Rủi ro | Mức độ | Biện pháp |
|---|---|---|
| Template thiếu status/ID | Cao | Khóa data contract trong Tuần 1 |
| Dữ liệu chưa được duyệt | Cao | Chỉ index trạng thái đã duyệt |
| Cam kết chính xác tuyệt đối | Cao | Evidence gate, citation và abstention |
| Cloud LLM không được phép nhận dữ liệu | Cao | Phê duyệt provider, giới hạn context, không gửi PII |
| Chỉ một người thực hiện | Cao | Khóa scope, ưu tiên P0, loại bỏ tính năng phụ |
| Embedding CPU chậm | Trung bình | Incremental embedding và benchmark model |
| LLM quota/timeout | Trung bình | Timeout, retry giới hạn, provider adapter |
| Metadata extraction sai | Cao | Hard filter, fallback và test theo đối tượng |
| API key bị lộ | Trung bình | Secret manager/env, rotation và không log |
| Google Sheets thay đổi cấu trúc | Cao | Schema/version validation |
| File đính kèm không tải được | Trung bình | Báo lỗi và không publish link hỏng |
| Qdrant lệch PostgreSQL | Trung bình | Rebuild index từ Silver |
| Prompt injection | Cao | Tách instruction/data và kiểm thử adversarial |
| Chèn hoặc đổi thứ tự dòng | Cao | Dùng mã nghiệp vụ, không dùng STT |

## 14. Thứ tự ưu tiên

### P0 — Bắt buộc

- Data validation.
- PostgreSQL.
- Qdrant.
- STAIR serialization.
- Routing.
- FAQ.
- RAG có citation.
- Abstention.
- API key.
- Web chat tối thiểu.
- Docker Compose.
- Evaluation.
- Runbook.

### P1 — Nên có

- Google Sheets live integration.
- PostgreSQL full-text retrieval.
- Presigned URL cho file.
- Structured metrics.
- Index rebuild command.
- Backup/restore script.

### P2 — Sau PoC

- Zalo.
- SSO.
- Admin portal.
- Scheduled sync.
- Nhiều phòng ban.
- Dashboard giám sát.
- Redis cache.
- Reranker chuyên biệt.
- High availability.

Nếu thiếu thời gian, cắt P2 trước, sau đó P1; không cắt P0.

## 15. Kế hoạch mở rộng sau PoC

Trước khi thêm 6 phòng ban còn lại:

1. Tổng kết KPI PoC.
2. Chuẩn hóa lại template dùng chung.
3. Xác nhận `department_id`.
4. Bổ sung tenant isolation integration tests.
5. Thay API key đơn bằng authentication phù hợp.
6. Xây onboarding checklist.
7. Benchmark dung lượng Qdrant và PostgreSQL.
8. Xác định chính sách backup và retention.
9. Triển khai phòng ban thứ hai để kiểm chứng isolation.
10. Chỉ mở rộng đồng loạt sau khi phòng ban thứ hai đạt UAT.

## 16. Exit checklist

- [ ] Data contract được xác nhận.
- [ ] Dữ liệu PoC được duyệt.
- [ ] Docker Compose hoạt động.
- [ ] Migration hoạt động.
- [ ] Sync idempotent.
- [ ] FAQ hoạt động.
- [ ] Routing hoạt động.
- [ ] RAG có citation.
- [ ] Abstention hoạt động.
- [ ] API key hoạt động.
- [ ] Web chat hoạt động.
- [ ] Tenant leakage test bằng 0.
- [ ] KPI đạt ngưỡng hoặc có báo cáo ngoại lệ.
- [ ] UAT hoàn tất.
- [ ] Runbook hoàn tất.
- [ ] Backup/restore được thử nghiệm.
- [ ] Hạn chế PoC được ghi nhận.
