# Data Dictionary — PoC Phòng Bảo đảm chất lượng / Mô-đun Khảo khí

## 1. Phạm vi

Data contract này áp dụng cho dữ liệu PoC tại `data/P.BDCL/`.

Mô hình phân cấp:

```text
Phòng ban (department)
└── Mô-đun (module)
    ├── Quy tắc phạm vi (routing rule)
    ├── FAQ
    └── Tài liệu nghiệp vụ
        ├── Nội dung quy định
        ├── Điều kiện/ngoại lệ/lỗi thường gặp
        ├── Thông tin thủ tục
        ├── Hồ sơ
        └── Các bước thực hiện
```

Một phòng ban có thể có nhiều mô-đun. PoC chỉ kích hoạt:

| Thuộc tính | Giá trị chuẩn |
|---|---|
| `department_id` | `bao_dam_chat_luong` |
| `department_name` | `Phòng Bảo đảm chất lượng` |
| `module_code` | `khao_khi` |
| `module_name` | `Mô-đun Khảo khí` |
| `audience` | `nguoi_hoc` |

`department_id` là định danh kỹ thuật đã được chốt từ đầu dự án và được giữ ổn định. Tên hiển thị có thể thay đổi mà không làm đổi ID.

## 2. Quy tắc chung

- Chuẩn hóa text về Unicode NFC.
- Trim khoảng trắng đầu/cuối và chuẩn hóa chuỗi khoảng trắng.
- Giữ nguyên nội dung nghiệp vụ sau khi chuẩn hóa kỹ thuật.
- Không tự sửa “Khảo khí” thành “Khảo thí”.
- Không dùng STT hoặc số dòng làm business key duy nhất.
- Mọi record phải lưu `source_file`, `source_sheet`, `source_row`.
- Mọi record phải thuộc cả `department_id` và `module_code`.
- Dữ liệu không có trạng thái tại dòng sẽ kế thừa trạng thái từ release manifest.
- Không dùng dữ liệu cho UAT khi release chưa ở trạng thái `approved_for_uat`.

## 3. Department

| Field | Kiểu | Bắt buộc | Nguồn | Quy tắc |
|---|---|---:|---|---|
| `id` | UUID | Có | Hệ thống | UUID nội bộ |
| `code` | string | Có | Cấu hình | `bao_dam_chat_luong` |
| `name` | string | Có | Cấu hình | `Phòng Bảo đảm chất lượng` |
| `audience` | enum | Có | Cấu hình | `nguoi_hoc` |
| `is_active` | boolean | Có | Cấu hình | `true` trong PoC |
| `created_at` | datetime | Có | Hệ thống | UTC |
| `updated_at` | datetime | Có | Hệ thống | UTC |

## 4. Module

Nguồn: `1. Thông tin Mô-đun - Khảo khí.xlsx`, sheet `1. Phạm vi trả lời`.

| Field | Kiểu | Bắt buộc | Ô/nguồn | Quy tắc |
|---|---|---:|---|---|
| `id` | UUID | Có | Hệ thống | UUID nội bộ |
| `department_id` | UUID | Có | Cấu hình | FK tới department |
| `code` | string | Có | Release manifest | `khao_khi` |
| `name` | string | Có | `C4` | `Mô-đun Khảo khí` |
| `source_created_at` | date | Không | `C5` | Ngày trong workbook |
| `source_updated_at` | date | Không | `C6` | Ngày trong workbook |
| `release_status` | enum | Có | Release manifest | Không suy ra từ workbook |
| `content_hash` | string | Có | Hệ thống | SHA-256 canonical content |
| `sync_run_id` | UUID | Có | Hệ thống | Lần đồng bộ gần nhất |

## 5. Routing rule

Nguồn: cùng workbook mô-đun, header tại `A9:G9`, dữ liệu bắt đầu từ dòng 10.

| Field | Kiểu | Bắt buộc | Cột nguồn | Quy tắc |
|---|---|---:|---|---|
| `id` | UUID | Có | Hệ thống | UUID nội bộ |
| `department_id` | UUID | Có | Cấu hình | Bắt buộc |
| `module_id` | UUID | Có | Cấu hình | Bắt buộc |
| `source_key` | string | Có | Hệ thống | Xem quy tắc định danh |
| `source_order` | integer | Có | A | Chỉ dùng sắp xếp, không dùng làm key |
| `scope_type` | enum | Có | B | Chuẩn hóa theo canonical enum |
| `topic` | text | Có | C | Chủ đề/tình huống |
| `bot_behavior` | text | Không | D | Có thể kế thừa behavior mặc định theo scope |
| `support_contact` | string | Không | E | Đầu mối handoff |
| `contact_information` | string | Không | F | Email/hotline |
| `online_channel` | URL/string | Không | G | Có thể trống |
| `release_status` | enum | Có | Manifest | Kế thừa release |
| `content_hash` | string | Có | Hệ thống | SHA-256 canonical row |

### 5.1. Định danh routing rule

Workbook hiện không có mã routing ổn định. PoC sử dụng:

```text
route:{sha256(department_id|module_code|scope_type|normalized_topic)[0:20]}
```

Hệ quả:

- Chèn hoặc đổi số thứ tự dòng không làm đổi key.
- Sửa nội dung `topic` tạo rule mới và deactivate rule cũ.
- `source_order` chỉ phục vụ hiển thị/audit.
- Khi mở rộng production nên bổ sung cột `MÃ PHẠM VI` tại nguồn.

## 6. FAQ

Nguồn: `2. FAQ - Câu hỏi thường gặp.xlsx`, sheet `1. FAQ`, header `B4:K4`.

| Field | Kiểu | Bắt buộc | Cột nguồn | Quy tắc |
|---|---|---:|---|---|
| `id` | UUID | Có | Hệ thống | UUID nội bộ |
| `department_id` | UUID | Có | Cấu hình | Bắt buộc |
| `module_id` | UUID | Có | Cấu hình | Bắt buộc |
| `question_code` | string | Có | C | Duy nhất trong module |
| `category` | string | Có | D | Phân mục cấp 1 |
| `subcategory` | string | Không | E | Phân mục chi tiết |
| `question` | text | Có | F | Câu hỏi gốc |
| `normalized_question` | text | Có | Hệ thống | Dùng exact/normalized match |
| `answer` | text | Có | G | Câu trả lời đã duyệt theo release |
| `legal_basis` | text | Không | H | Nullable |
| `support_contact` | string | Không | I | Nếu trống, kế thừa module default |
| `contact_information` | string | Không | J | Nếu trống, kế thừa module default |
| `online_channel` | string | Không | K | Nếu trống, kế thừa module default |
| `release_status` | enum | Có | Manifest | Workbook không có status dòng |
| `content_hash` | string | Có | Hệ thống | SHA-256 canonical row |

### 6.1. Định danh FAQ

Business key:

```text
department_id + module_code + question_code
```

`STT` không tham gia business key.

### 6.2. FAQ thiếu văn bản căn cứ

- `legal_basis` được phép null.
- FAQ không có văn bản căn cứ vẫn có thể dùng trong môi trường development nếu release là `approved_for_dev`.
- FAQ chỉ được dùng trong UAT nếu toàn bộ release được chuyên viên chuyển sang `approved_for_uat`.
- Citation tối thiểu là `question_code`, tên workbook và vị trí dòng nguồn.
- Hệ thống không được tự tạo số hiệu văn bản căn cứ.

## 7. Document

Nguồn: `3. Tài liệu nghiệp vụ.xlsx`, các sheet `Tài liệu 1` đến `Tài liệu 4`.

| Field | Kiểu | Bắt buộc | Nguồn | Quy tắc |
|---|---|---:|---|---|
| `id` | UUID | Có | Hệ thống | UUID nội bộ |
| `department_id` | UUID | Có | Cấu hình | Bắt buộc |
| `module_id` | UUID | Có | Cấu hình | Bắt buộc |
| `document_code` | string | Có | `C1` | Chuẩn hóa `CHỦ ĐỀ TL01` → `TL01` |
| `title` | string | Có | `C4` | Tên chủ đề |
| `summary` | text | Có | `C5` | Tóm tắt |
| `aliases` | array[string] | Không | `C6` | Split bằng dấu `;` |
| `document_type` | enum | Có | Suy ra có kiểm soát | TL01=`regulation`, TL02–TL04=`procedure` |
| `release_status` | enum | Có | Manifest | Kế thừa release |
| `effective_from` | date | Không | Manifest/nguồn tương lai | Null trong dữ liệu hiện tại |
| `effective_to` | date | Không | Manifest/nguồn tương lai | Null trong dữ liệu hiện tại |
| `content_hash` | string | Có | Hệ thống | SHA-256 canonical document |

Business key:

```text
department_id + module_code + document_code
```

## 8. Document section

### 8.1. Nội dung quy định

Nguồn: section B, header tại `A9:F9`.

| Field | Cột |
|---|---|
| `source_order` | A |
| `category` | B |
| `subcategory` | C |
| `content` | D |
| `condition` | E |
| `resolution` | F |

### 8.2. Điều kiện, ngoại lệ, lỗi thường gặp

Nguồn: section C, header tại `A22:E22`.

| Field | Cột |
|---|---|
| `source_order` | A |
| `scenario` | B |
| `resolution` | D |
| `condition_type` | E |

### 8.3. Định danh section

```text
section:{sha256(document_code|section_type|normalized_heading|source_order)[0:20]}
```

`source_order` được dùng để phân biệt các heading trùng trong cùng tài liệu. Việc sửa heading được xem là thay section.

## 9. Procedure

Nguồn: section D, nhãn `B35:B43`, giá trị tại cột C.

| Field | Nhãn nguồn |
|---|---|
| `result` | Kết quả người học nhận được |
| `processing_time_type` | Thời hạn xử lý |
| `max_working_days` | Số ngày làm việc tối đa |
| `location` | Địa điểm |
| `submission_url` | Link nộp/cổng trực tuyến |
| `special_schedule` | Lịch tiếp nhận đặc biệt |
| `fee_type` | Lệ phí |
| `fee_amount_vnd` | Số tiền |
| `fee_note` | Ghi chú lệ phí/hình thức nộp |

### 9.1. Chính sách lệ phí chưa xác định

TL02, TL03 và TL04 hiện có ghi chú “Chưa xác định”.

- `fee_type=unknown`.
- `fee_amount_vnd=null`.
- Không trả lời một mức tiền cụ thể.
- Trạng thái trả lời phải là `insufficient_evidence` hoặc `human_handoff`.
- Không được dùng kiến thức chung hoặc suy luận từ thủ tục khác.

## 10. Dossier item

Nguồn: section E, header tại `A46:E46`.

| Field | Cột |
|---|---|
| `source_order` | A |
| `name` | B |
| `form_url` | C |
| `quantity_specification` | D |
| `is_required` | E |

`is_required` chuẩn hóa `Có` → `true`, `Không` → `false`.

## 11. Procedure step

Nguồn: section F, header tại `A59:F59`.

| Field | Cột |
|---|---|
| `step_number` | A |
| `instruction` | B |
| `url_or_location` | C |
| `responsible_unit` | D |
| `time_requirement` | E |
| `channel` | F |

Business key:

```text
document_code + step_number
```

## 12. Contact inheritance

PoC sử dụng thứ tự:

1. Contact tại record.
2. Contact mặc định của module trong cấu hình đã được xác nhận.
3. Contact mặc định của department.
4. Nếu không có contact đã xác nhận: không tự tạo, trả về `support_contact=null`.

Contact quan sát được trong workbook:

- Đơn vị sau chuẩn hóa: `Phòng Bảo đảm chất lượng`.
- Email: `phongbdcl@uel.edu.vn`.
- Hotline: `19001239`.

Các giá trị này chỉ được đánh dấu “đã xác minh để công bố” sau UAT/business approval.

## 13. Source metadata bắt buộc

Mỗi record Silver phải có:

- `source_file`.
- `source_file_sha256`.
- `source_schema_sha256`.
- `source_sheet`.
- `source_row`.
- `source_cell_range` nếu có.
- `sync_run_id`.
- `ingested_at`.
- `release_id`.
- `content_hash`.

## 14. Cardinality

```text
departments 1 ── N modules
modules     1 ── N routing_rules
modules     1 ── N faqs
modules     1 ── N documents
documents   1 ── N document_sections
documents   1 ── 0..1 procedures
documents   1 ── N dossier_items
documents   1 ── N procedure_steps
sync_runs   1 ── N source_records
```
