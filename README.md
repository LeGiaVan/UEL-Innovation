# 8 chatbot phòng — UEL

Mỗi phòng một thư mục, một Compose, Mongo + Qdrant riêng, một domain. Code gốc: `starter/`. Bản copy: `phong-*/`, `vien-quoc-te/`.

**Demo đang chạy:** `starter/` → http://localhost:8000

## Bắt đầu deploy

1. Đọc **[docs/deploy.md](docs/deploy.md)** — checklist máy phòng, `.env`, Google, Excel.
2. Chọn thư mục phòng, điền cấu hình, chạy:

```bash
cd phong-dao-tao
cp .env.example .env
# điền JWT_SECRET, GOOGLE_CLIENT_ID, LLM_API_KEY, COOKIE_SECURE=true
# sửa chatbot-api/configs/department.yaml (admins, form)
docker compose -f docker-compose.prod.yml up -d --build
```

Mẫu Excel trống: `template/`.

## Tài liệu

| File | Việc |
|---|---|
| [docs/deploy.md](docs/deploy.md) | Bàn giao + checklist 8 phòng |
| [docs/api.md](docs/api.md) | Cookie, Origin, ai gọi được API |
| [GIAI_DOAN.md](GIAI_DOAN.md) | Pha đã làm (P0–P9) |
| [PLAN_UPDATE.md](PLAN_UPDATE.md) | Đặc tả đã khóa |
| [bao-cao-giai-doan/](bao-cao-giai-doan/) | Báo cáo từng pha |
| [starter/README.md](starter/README.md) | Chạy demo / dev |

Không dùng Postgres, MinIO, ticket, login mật khẩu. Không image registry chung — mỗi máy `compose build` tại chỗ.
