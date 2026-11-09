# Schema Fingerprints — PoC P.BDCL

## 1. Thuật toán

### File checksum

```text
SHA-256(raw file bytes)
```

Checksum thay đổi khi bất kỳ byte nào trong workbook thay đổi.

### Schema fingerprint

```text
SHA-256(canonical JSON của sheet names + metadata labels + section/header labels)
```

Canonical JSON:

- UTF-8.
- Key được sắp xếp.
- Không có khoảng trắng không cần thiết.
- Giữ nguyên text label sau khi đọc từ workbook.

Schema fingerprint phát hiện thay đổi cấu trúc nhưng không thay đổi khi chỉ sửa nội dung FAQ/tài liệu.

## 2. Baseline ngày 2026-11-09

| File | File SHA-256 | Schema SHA-256 |
|---|---|---|
| `1. Thông tin Mô-đun - Khảo khí.xlsx` | `01f847bb40448d37dcdfdc6de0c681263146223f76afa501f7839a17e4f4b9df` | `2e0b929ed54f92ac0b67ef8598ed831aeb5d4b6303c9dcd838b8526a929ca658` |
| `2. FAQ - Câu hỏi thường gặp.xlsx` | `d79630b9d492394704361b64d0ca71077e8fd74e3f0e12bc6b9cab529ed75c4a` | `bfa822225f0c5f28aec5d0e4bebf61bd85c519a6d58c9a571d1a9f89134168a6` |
| `3. Tài liệu nghiệp vụ.xlsx` | `39c1e025b79047812ae989952591d68ea489e500e37685d3ed11cbefa39f71d0` | `9d4b95081796c7134366b0517eabc273ffdf28d01845e4bb7fb4bb98c960cfae` |

## 3. Schema mô-đun

Sheets:

- `0. Hướng dẫn`.
- `1. Phạm vi trả lời`.

Metadata labels:

- `Tên Mô-đun`.
- `Ngày tạo`.
- `Ngày cập nhật`.

Routing header:

1. `STT`.
2. `Phạm vi MÔ-ĐUN`.
3. `Chủ đề / tình huống`.
4. `Cách chatbot xử lý`.
5. `Đầu mối hỗ trợ (nếu cần)`.
6. `Thông tin liên hệ (nếu cần)`.
7. `Kênh trực tuyến (link Fanpage / Zalo / cổng ticket)`.

## 4. Schema FAQ

Sheets:

- `0. Hướng dẫn`.
- `1. FAQ`.

FAQ header:

1. `STT`.
2. `MÃ CÂU HỎI`.
3. `PHÂN MỤC`.
4. `PHÂN MỤC CHI TIẾT`.
5. `CÂU HỎI`.
6. `CÂU TRẢ LỜI`.
7. `VĂN BẢN CĂN CỨ (LOẠI, SỐ HIỆU, NGÀY BAN HÀNH) (NẾU CÓ)`.
8. `ĐẦU MỐI HỖ TRỢ (NẾU CẦN)`.
9. `THÔNG TIN LIÊN HỆ (NẾU CẦN)`.
10. `KÊNH TRỰC TUYẾN (NẾU CẦN)`.

## 5. Schema tài liệu nghiệp vụ

Sheets baseline:

- `Hướng dẫn`.
- `Tài liệu 1`.
- `Tài liệu 2`.
- `Tài liệu 3`.
- `Tài liệu 4`.
- `MẪU`.
- `_DS`.

Section markers:

1. `A. THÔNG TIN CHUNG`.
2. `B. NỘI DUNG QUY ĐỊNH`.
3. `C. ĐIỀU KIỆN, NGOẠI LỆ, LỖI THƯỜNG GẶP`.
4. `D. THỰC HIỆN THỦ TỤC`.
5. `E. HỒ SƠ CẦN CHUẨN BỊ`.
6. `F. CÁC BƯỚC THỰC HIỆN`.

Các header chi tiết được mô tả trong `docs/data-mapping.md`.

## 6. Chính sách schema drift

| Tình huống | Hành vi |
|---|---|
| File checksum đổi, schema fingerprint giữ nguyên | Cho phép tạo release mới và chạy validation |
| File checksum giữ nguyên | Không cần ingest lại |
| Schema fingerprint đổi | Dừng sync và yêu cầu cập nhật parser/data contract |
| Thêm sheet `Tài liệu N` đúng schema | Cho phép sau khi parser xác nhận |
| Đổi tên sheet dữ liệu | Dừng sync |
| Đổi header/cột | Dừng sync |
| Chỉ đổi formatting | File checksum có thể đổi; schema fingerprint phải giữ nguyên |

## 7. Giới hạn

- Fingerprint không chứng minh nội dung đúng nghiệp vụ.
- Fingerprint không thay thế validation.
- Công thức, data validation và style chưa tham gia schema fingerprint Phase 0.
- Khi production hóa cần version hóa thuật toán fingerprint.
