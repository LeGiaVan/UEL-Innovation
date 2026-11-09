# Báo cáo Phase 0 — Baseline, kiểm kê và khóa dữ liệu PoC

## 1. Metadata

| Thuộc tính | Giá trị |
|---|---|
| Phase | 0 |
| Trạng thái | `ACCEPTED` |
| Ngày bắt đầu | 2026-11-09 |
| Ngày kết thúc | 2026-11-09 |
| Phạm vi | Phòng Bảo đảm chất lượng / Mô-đun Khảo khí |
| `department_id` | `bao_dam_chat_luong` |
| `module_code` | `khao_khi` |
| Người thực hiện | Lê Gia Văn / dự án UEL Innovation |

## 2. Mục tiêu

- Kiểm kê dữ liệu PoC thực tế.
- Xác định quan hệ department–module.
- Khóa data contract cho parser/pipeline.
- Định nghĩa approval policy khi workbook thiếu row-level status.
- Xác định schema fingerprints.
- Ghi nhận giới hạn dữ liệu trước khi phát triển.

## 3. Kết quả kiểm kê

### 3.1. Nguồn dữ liệu

Đã nhận đủ:

1. `1. Thông tin Mô-đun - Khảo khí.xlsx`.
2. `2. FAQ - Câu hỏi thường gặp.xlsx`.
3. `3. Tài liệu nghiệp vụ.xlsx`.

### 3.2. Routing

| Loại | Số lượng |
|---|---:|
| Bot được trả lời | 8 |
| Cần cán bộ hỗ trợ | 5 |
| Ngoài phạm vi | 4 |
| Tổng | 17 |

### 3.3. FAQ

| Chỉ số | Kết quả |
|---|---:|
| Tổng FAQ | 71 |
| Thiếu mã | 0 |
| Thiếu câu hỏi | 0 |
| Thiếu câu trả lời | 0 |
| Mã trùng | 0 |
| Thiếu văn bản căn cứ | 59 |
| Thiếu contact riêng | 71 |

### 3.4. Tài liệu

| Mã | Nội dung quy định | Điều kiện/ngoại lệ | Hồ sơ | Bước |
|---|---:|---:|---:|---:|
| TL01 | 8 | 10 | 0 | 0 |
| TL02 | 3 | 6 | 1 | 5 |
| TL03 | 2 | 6 | 2 | 4 |
| TL04 | 2 | 4 | 1 | 4 |
| Tổng | 15 | 26 | 4 | 13 |

## 4. Checklist hoàn thành

- [x] Xác nhận đủ ba workbook.
- [x] Kiểm kê sheet, header và vùng dữ liệu.
- [x] Kiểm kê routing rules.
- [x] Kiểm kê FAQ và duplicate/required fields.
- [x] Kiểm kê TL01–TL04.
- [x] Xác nhận “Khảo khí” là tên đúng.
- [x] Chốt tên phòng ban `Phòng Bảo đảm chất lượng`.
- [x] Chốt `module_code=khao_khi`.
- [x] Chốt stable ID policy.
- [x] Chốt release/approval policy.
- [x] Chốt contact inheritance policy.
- [x] Chốt policy cho FAQ thiếu căn cứ.
- [x] Chốt policy cho lệ phí chưa xác định.
- [x] Ghi contact/URL verification thành UAT release gate.
- [x] Chốt cloud LLM ở mức thiết kế và giới hạn không gửi PII.
- [x] Hoàn thành data dictionary.
- [x] Hoàn thành canonical enums.
- [x] Hoàn thành data mapping.
- [x] Tạo schema fingerprints.
- [x] Tạo release manifest.

## 5. Deliverables

| Deliverable | Đường dẫn | Trạng thái |
|---|---|---|
| Data dictionary | `docs/data-dictionary.md` | Hoàn thành |
| Data mapping | `docs/data-mapping.md` | Hoàn thành |
| Canonical enums | `docs/canonical-enums.md` | Hoàn thành |
| Approval policy | `docs/data-approval-policy.md` | Hoàn thành |
| Schema fingerprints | `docs/schema-fingerprints.md` | Hoàn thành |
| Decision record | `docs/decisions/phase-00-decisions.md` | Hoàn thành |
| Release manifest | `data/P.BDCL/release-manifest.yaml` | Hoàn thành |
| Phase reporting template | `reports/phases/_TEMPLATE.md` | Hoàn thành |

## 6. Checksum evidence

| File | File SHA-256 | Schema SHA-256 |
|---|---|---|
| Module | `01f847bb40448d37dcdfdc6de0c681263146223f76afa501f7839a17e4f4b9df` | `2e0b929ed54f92ac0b67ef8598ed831aeb5d4b6303c9dcd838b8526a929ca658` |
| FAQ | `d79630b9d492394704361b64d0ca71077e8fd74e3f0e12bc6b9cab529ed75c4a` | `bfa822225f0c5f28aec5d0e4bebf61bd85c519a6d58c9a571d1a9f89134168a6` |
| Documents | `39c1e025b79047812ae989952591d68ea489e500e37685d3ed11cbefa39f71d0` | `9d4b95081796c7134366b0517eabc273ffdf28d01845e4bb7fb4bb98c960cfae` |

## 7. Exit gate

| Điều kiện | Kết quả | Ghi chú |
|---|---|---|
| Tên module rõ ràng | Pass | “Khảo khí” là tên đúng |
| Department/module hierarchy rõ ràng | Pass | Một phòng có nhiều module; PoC cố định một module |
| Business keys được định nghĩa | Pass | Không dùng STT làm key |
| Approval policy được định nghĩa | Pass | Release manifest |
| Dữ liệu thiếu có policy | Pass | Warning/abstain/handoff |
| Schema drift policy được định nghĩa | Pass | Dùng schema fingerprint |
| Cloud LLM có giới hạn dữ liệu | Pass | Không gửi PII; cần organizational approval trước UAT |

## 8. Quyết định chính

1. Một department có nhiều module.
2. PoC chỉ chạy `bao_dam_chat_luong/khao_khi`.
3. Mọi record và vector phải có cả department và module.
4. Release hiện tại là `approved_for_dev`, chưa được phép UAT.
5. FAQ thiếu căn cứ vẫn được dùng trong development với warning.
6. Contact được kế thừa theo policy, không tự suy ra.
7. Lệ phí chưa xác định không được LLM suy đoán.
8. XLSX là adapter đầu tiên; Google Sheets dùng cùng canonical model.

## 9. Hạn chế chuyển tiếp

Các mục sau không chặn Phase 1–6 trong development nhưng chặn UAT:

| ID | Nội dung | Release gate |
|---|---|---|
| UAT-01 | Business approval cho 71 FAQ và TL01–TL04 | Trước Phase 9 |
| UAT-02 | Xác minh email, hotline và URL | Trước Phase 9 |
| UAT-03 | Xác nhận policy lệ phí TL02–TL04 | Trước Phase 9 |
| UAT-04 | Chấp nhận/bổ sung căn cứ cho 59 FAQ | Trước Phase 9 |
| UAT-05 | Organizational approval cho cloud LLM | Trước Phase 9 |

## 10. Rủi ro chuyển Phase 1

- Parser phải dùng schema fingerprint vì workbook PoC khác template gốc.
- Release manifest phải được kiểm tra trước mọi sync.
- Không được hard-code giả định một department chỉ có một module.
- Qdrant payload và SQL uniqueness phải bao gồm module.

## 11. Kết luận

**Kết quả: `ACCEPTED`**

Phase 0 đã hoàn thành về mặt discovery và data contract. Dữ liệu được phép dùng cho development/test theo release manifest. Phase 1 có thể bắt đầu; UAT vẫn phải vượt các release gate được ghi ở trên.
