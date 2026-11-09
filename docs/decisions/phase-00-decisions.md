# Phase 0 Decision Record

Ngày chốt: 2026-11-09.

## DR-000 — Phạm vi PoC

**Trạng thái:** Accepted

PoC triển khai cho:

- Department: Phòng Bảo đảm chất lượng.
- Department ID: `bao_dam_chat_luong`.
- Module: Khảo khí.
- Module code: `khao_khi`.

Không triển khai các mô-đun khác của phòng trong PoC.

## DR-001 — Một phòng ban có nhiều mô-đun

**Trạng thái:** Accepted

Quan hệ:

```text
department 1 ── N modules
```

Routing rule, FAQ, document, vector và sync record đều phải có cả department và module context.

PoC inject cố định:

```text
department_id=bao_dam_chat_luong
module_code=khao_khi
```

## DR-002 — “Khảo khí” là tên đúng

**Trạng thái:** Accepted

Không tự sửa tên file, tên module hoặc display value thành “Khảo thí”.

Các nội dung nghiệp vụ bên trong có thể đề cập “khảo thí”; đó là nội dung của Mô-đun Khảo khí, không phải căn cứ đổi tên module.

## DR-003 — Tên phòng ban

**Trạng thái:** Accepted

Tên hiển thị chuẩn:

```text
Phòng Bảo đảm chất lượng
```

Các biến thể chữ hoa/thường trong nguồn được map về tên hiển thị chuẩn nhưng raw value vẫn được lưu để audit.

## DR-004 — Stable IDs

**Trạng thái:** Accepted

- FAQ: `department_id + module_code + question_code`.
- Document: `department_id + module_code + document_code`.
- Procedure step: `document_code + step_number`.
- Routing: hash của department, module, scope và normalized topic.
- Internal IDs: UUID.

Không dùng STT làm business key.

## DR-005 — Approval không nằm đầy đủ trong workbook

**Trạng thái:** Accepted

Dùng release manifest làm approval envelope.

Release hiện tại:

- Được phép development/test.
- Chưa được coi là business-approved cho UAT.

## DR-006 — FAQ thiếu văn bản căn cứ

**Trạng thái:** Accepted

`legal_basis` nullable. FAQ thiếu căn cứ:

- Có warning.
- Có thể dùng trong development nếu release được approve cho dev.
- Citation trỏ về FAQ source.
- Không tự sinh căn cứ.
- Cần business review trước UAT.

## DR-007 — Contact inheritance

**Trạng thái:** Accepted

Thứ tự:

1. Record contact.
2. Module default đã xác nhận.
3. Department default đã xác nhận.
4. Null.

Không tự suy ra contact.

## DR-008 — Lệ phí chưa xác định

**Trạng thái:** Accepted

TL02, TL03 và TL04:

- `fee_type=unknown`.
- Không nêu số tiền.
- Trả `insufficient_evidence` hoặc handoff khi người dùng hỏi phí.

## DR-009 — Cloud LLM

**Trạng thái:** Accepted cho thiết kế; cần organizational approval trước UAT

- Cloud LLM là mặc định của PoC vì server CPU-only.
- Chỉ gửi context nghiệp vụ tối thiểu.
- Không gửi dữ liệu cá nhân.
- Câu hỏi về trường hợp cá nhân phải handoff trước generation.
- Provider phải cấu hình được.

## DR-010 — XLSX là nguồn PoC đầu tiên

**Trạng thái:** Accepted

- Phase 2 triển khai XLSX adapter trước.
- Google Sheets adapter là bước tiếp theo, dùng cùng canonical model.
- Parser nhận diện schema bằng fingerprint, không chỉ bằng tên file.

## DR-011 — Hard filters

**Trạng thái:** Accepted

Mọi retrieval phải lọc tối thiểu:

```text
department_id
module_code
release_status
effective date khi có
```

LLM không được thay đổi hoặc loại bỏ hard filter.

## DR-012 — Source of truth

**Trạng thái:** Accepted

- XLSX/Google Sheets: nguồn quản trị.
- PostgreSQL Silver: nguồn chân lý vận hành đã chuẩn hóa.
- Qdrant Gold: index có thể rebuild.
- MinIO Bronze: snapshot và audit artifact.

Nếu Qdrant không đồng nhất, rebuild từ PostgreSQL.

## DR-013 — Exact FAQ trước RAG

**Trạng thái:** Accepted

Thứ tự:

1. Routing.
2. FAQ normalized exact match.
3. Metadata extraction.
4. Retrieval.
5. Evidence gate.
6. Generation.

FAQ exact match không gọi generation LLM.

## DR-014 — Không trả lời khi thiếu bằng chứng

**Trạng thái:** Accepted

- Không cam kết chính xác tuyệt đối.
- Không cho LLM dùng kiến thức chung để bổ sung quy định UEL.
- Không đủ bằng chứng → clarification, abstention hoặc handoff.
- Mọi câu RAG phải có citation.

## DR-015 — Báo cáo theo phase

**Trạng thái:** Accepted

Báo cáo được lưu tại:

```text
reports/phases/
```

Mỗi phase có một file `phase-XX.md` tạo từ `_TEMPLATE.md`.
