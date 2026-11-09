# Canonical Enums — UEL RAG Chatbot PoC

Các enum trong tài liệu này là giá trị nội bộ. Giá trị hiển thị trong XLSX được map về canonical value nhưng không bị sửa tại nguồn.

## 1. Department audience

| Source/display | Canonical |
|---|---|
| Người học | `nguoi_hoc` |
| Công nhân viên chức | `cong_nhan_vien_chuc` |

PoC: `nguoi_hoc`.

## 2. Routing scope

| Source value | Canonical | Hành vi |
|---|---|---|
| Trong phạm vi trả lời | `answer_allowed` | Cho phép FAQ/RAG |
| Trong phạm vi - bot không tự trả lời & cần cán bộ hỗ trợ | `human_required` | Không kết luận trường hợp cá nhân |
| Ngoài phạm vi trả lời | `out_of_scope` | Chuyển đơn vị phụ trách |

Giá trị không khớp mapping: validation `ERROR`.

## 3. Release status

| Canonical | Ý nghĩa |
|---|---|
| `candidate` | Dữ liệu đã nhận nhưng chưa được phép index |
| `approved_for_dev` | Được phép dùng trong development và automated test |
| `approved_for_uat` | Được chuyên viên chấp nhận để dùng trong UAT |
| `retired` | Ngưng sử dụng, giữ lại audit |

Không map `approved_for_dev` thành phê duyệt nghiệp vụ chính thức.

## 4. Document type

| Canonical | Ý nghĩa |
|---|---|
| `regulation` | Quy định/chính sách, không có thủ tục thực hiện |
| `procedure` | Thủ tục/quy trình |
| `regulation_and_procedure` | Có cả nội dung quy định và thủ tục |

Mapping PoC:

| Document | Canonical |
|---|---|
| TL01 | `regulation` |
| TL02 | `regulation_and_procedure` |
| TL03 | `regulation_and_procedure` |
| TL04 | `regulation_and_procedure` |

## 5. Section type

| Canonical | Nguồn |
|---|---|
| `regulation` | Section B |
| `condition` | Section C, loại Điều kiện |
| `exception` | Section C, loại Ngoại lệ |
| `common_error` | Section C, loại Lỗi thường gặp |
| `note` | Section C, loại Lưu ý |
| `procedure_metadata` | Section D |
| `dossier_item` | Section E |
| `procedure_step` | Section F |

## 6. Condition type

| Source | Canonical |
|---|---|
| Điều kiện | `condition` |
| Ngoại lệ | `exception` |
| Lỗi thường gặp | `common_error` |
| Lưu ý | `note` |

## 7. Processing time type

| Source | Canonical |
|---|---|
| Trong ngày | `same_day` |
| N ngày làm việc | `working_days` |
| Tùy trường hợp | `case_by_case` |
| Trống | `not_applicable` |

Nếu canonical là `working_days`, `max_working_days` phải là số nguyên dương.

## 8. Fee type

| Source/condition | Canonical |
|---|---|
| Không thu phí | `free` |
| Có thu phí cố định | `fixed` |
| Tùy trường hợp | `case_by_case` |
| Ghi chú chứa “Chưa xác định” | `unknown` |
| Trống ở tài liệu không phải thủ tục | `not_applicable` |

Quy tắc:

- `fixed` yêu cầu `fee_amount_vnd > 0`.
- `free` yêu cầu `fee_amount_vnd` bằng null hoặc 0.
- `unknown` bắt buộc `fee_amount_vnd=null` và không được sinh số tiền.

## 9. Answer status

| Canonical | Ý nghĩa |
|---|---|
| `faq_answered` | Trả lời từ FAQ |
| `answered` | Trả lời từ RAG có citation |
| `human_handoff` | Cần cán bộ hỗ trợ |
| `out_of_scope` | Không thuộc mô-đun |
| `insufficient_evidence` | Không đủ dữ liệu đã duyệt |
| `clarification_required` | Cần người dùng bổ sung đối tượng/ngữ cảnh |
| `error` | Lỗi kỹ thuật được kiểm soát |

## 10. Validation severity

| Canonical | Hành vi |
|---|---|
| `error` | Không publish release |
| `warning` | Có thể publish theo policy nhưng phải báo cáo |
| `info` | Ghi nhận biến đổi/kế thừa |

## 11. Sync status

| Canonical | Ý nghĩa |
|---|---|
| `started` | Đã bắt đầu |
| `validating` | Đang validate |
| `validation_failed` | Validation có lỗi chặn |
| `loading_silver` | Đang ghi PostgreSQL |
| `indexing_gold` | Đang ghi Qdrant |
| `completed` | Thành công toàn bộ |
| `partial_failed` | Silver thành công nhưng Gold hoặc artifact thất bại |
| `failed` | Thất bại |

## 12. Source type

| Canonical | Ý nghĩa |
|---|---|
| `xlsx` | File XLSX local/được upload |
| `google_sheets` | Google Sheets |

PoC bắt đầu với `xlsx`.

## 13. Environment

| Canonical | Release được phép |
|---|---|
| `development` | `approved_for_dev`, `approved_for_uat` |
| `test` | `approved_for_dev`, `approved_for_uat` |
| `uat` | Chỉ `approved_for_uat` |
| `production` | Chưa nằm trong phạm vi PoC |
