# Báo cáo giai đoạn — 8 chatbot phòng

Mỗi pha trong `GIAI_DOAN.md` kết thúc bằng một file trong thư mục này. Đặc tả: `PLAN_UPDATE.md`.

Không ghi secret, API key, cookie, mật khẩu, hay dữ liệu cá nhân.

## File

| Pha | File | Trạng thái lúc tạo thư mục |
|---|---|---|
| P0 | `P0.md` | `READY_FOR_REVIEW` |
| P1 | `P1.md` | `ACCEPTED` |
| P2 | `P2.md` | `ACCEPTED` |
| P3 | `P3.md` | `ACCEPTED` |
| P4 | `P4.md` | `ACCEPTED` |
| P5 | `P5.md` | `READY_FOR_REVIEW` |
| P6 | `P6.md` | `NOT_STARTED` — chốt starter (Docker + gold + độ trễ), chưa clone |
| P7 | `P7.md` | `NOT_STARTED` — clone starter, phòng deploy ngay |

Mẫu trống: `_TEMPLATE.md`.

## Trạng thái

| Giá trị | Ý nghĩa |
|---|---|
| `NOT_STARTED` | Chưa code pha này |
| `IN_PROGRESS` | Đang làm |
| `BLOCKED` | Thiếu quyết định / máy / key |
| `READY_FOR_REVIEW` | Xong kỹ thuật, chờ duyệt |
| `ACCEPTED` | Đạt cửa ra |

Chỉ đánh dấu checklist khi có bằng chứng (lệnh, đường dẫn file, hành vi UI) — không đánh dấu vì “đã định làm”.
