# Báo cáo theo phase

Thư mục này lưu báo cáo nghiệm thu sau khi hoàn thành từng phase trong `PHASE_PLAN.md`.

## Quy ước tên file

```text
phase-00.md
phase-01.md
...
phase-09.md
```

Sử dụng `_TEMPLATE.md` để tạo báo cáo mới.

## Trạng thái báo cáo

| Status | Ý nghĩa |
|---|---|
| `DRAFT` | Đang thực hiện phase |
| `READY_FOR_REVIEW` | Đã hoàn thành kỹ thuật, chờ review |
| `ACCEPTED` | Đạt exit gate |
| `ACCEPTED_WITH_EXCEPTIONS` | Được chấp nhận với ngoại lệ đã ghi rõ |
| `REJECTED` | Không đạt exit gate |

## Báo cáo hiện có

| Phase | File | Trạng thái |
|---:|---|---|
| 0 | `phase-00.md` | `ACCEPTED` |
| 1 | `phase-01.md` | `ACCEPTED` |
| 2 | `phase-02.md` | `ACCEPTED` |
| 3 | `phase-03.md` | `ACCEPTED` |
| 4 | `phase-04.md` | `ACCEPTED` |
| 5 | `phase-05.md` | `ACCEPTED` |
| 6 | `phase-06.md` | `ACCEPTED` |

## Yêu cầu tối thiểu

Mỗi báo cáo phải có:

- Phạm vi phase.
- Ngày bắt đầu/kết thúc.
- Checklist đã hoàn thành.
- Deliverables.
- Kết quả exit gate.
- Test/evidence.
- Quyết định.
- Blocker còn lại.
- Rủi ro chuyển tiếp.
- Người hoặc tiêu chí chấp nhận.

Không đưa secret, API key hoặc dữ liệu cá nhân vào báo cáo.
