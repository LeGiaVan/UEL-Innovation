# Deploy một phòng rồi bung 8

Không thay `PLAN_UPDATE.md`. Demo: `starter/` → http://localhost:8000. Tám thư mục phòng là bản copy code, **chưa** phải máy đang chạy.

Một phòng = một máy (hoặc VM) + một Compose + Mongo riêng + Qdrant riêng + một domain. Vá bug trên `starter/` rồi `python scripts/clone_starter.py` (không mang seed Khảo thí).

---

## 1. Ba lớp

| Lớp | Thư mục | Việc |
|---|---|---|
| Demo | `starter/` | Login Google, nạp Excel thử, chat. Có seed Khảo thí. |
| Copy | `phong-*/`, `vien-quoc-te/` | Cùng code. `modules: []`, `admins: []`. Điền file rồi mới `compose`. |
| Máy phòng | VM + domain | Cán bộ nạp tri thức trên `/quan-ly`. Không sửa Python/JS. |

Không share Mongo / Qdrant / cookie giữa các phòng.

---

## 2. Tám phòng

| Thư mục | `DEPARTMENT_ID` | Domain |
|---|---|---|
| `phong-hanh-chinh/` | `hc` | `hc.chat.uel.edu.vn` |
| `phong-tuyen-sinh-cong-tac-sinh-vien/` | `ctsv` | `ctsv.chat.uel.edu.vn` |
| `phong-dao-tao/` | `pdt` | `pdt.chat.uel.edu.vn` |
| `phong-quan-tri-tai-san/` | `qtts` | `qtts.chat.uel.edu.vn` |
| `vien-quoc-te/` | `vqt` | `vqt.chat.uel.edu.vn` |
| `phong-nhan-su/` | `pns` | `pns.chat.uel.edu.vn` |
| `phong-khoa-hoc-cong-nghe/` | `khcn` | `khcn.chat.uel.edu.vn` |
| `phong-bao-dam-chat-luong/` | `dbcl` | `dbcl.chat.uel.edu.vn` |

Gợi ý bung trước: **Đào tạo** hoặc **ĐBCL**. Không chạy 8 Compose trên một máy (cổng `8000`, RAM BGE).

---

## 3. Trước `compose up` phòng đầu

| # | Việc |
|---|---|
| 1 | Docker + Compose, RAM ≥ 8GB |
| 2 | DNS domain phòng |
| 3 | HTTPS (Nginx/Caddy/Traefik) — Compose chưa có TLS |
| 4 | `.env`: `DEPARTMENT_ID`, `JWT_SECRET` riêng, `GOOGLE_CLIENT_ID` riêng, `LLM_API_KEY` |
| 5 | `COOKIE_SECURE=true` khi đã HTTPS |
| 6 | Google: một Client ID / phòng; origin = `https://<domain>` |
| 7 | yaml: `admins` `@uel.edu.vn`, `handoff_form_url` form thật. Không bật `allow_non_uel_admin` |
| 8 | Dùng `docker-compose.prod.yml` (không mở Qdrant ra host, không mount `app/`) |

Copy lại starter mới nhất trước khi bung: `python scripts/clone_starter.py`.

---

## 4. Lên một phòng

```text
cd phong-dao-tao          # ví dụ
cp .env.example .env      # điền secret
# sửa chatbot-api/configs/department.yaml
docker compose -f docker-compose.prod.yml up -d --build
```

Lần đầu 20–40 phút (BGE-M3 trong image).

1. `/health/ready` = ok.
2. Login Google admin → header đúng **tên phòng**.
3. `/quan-ly` → tạo mảng → nạp đủ 5 Excel 3.0 (`template/` ở gốc repo).
4. Người hỏi: 1 FAQ + 1 câu RAG.
5. Member không vào `/quan-ly`.

File 04/05 được trống (cảnh báo). Sai Excel = 422, bản nạp cũ còn.

---

## 5. Cán bộ tự quản (không cần dev)

| Việc | Ở đâu |
|---|---|
| Thêm mảng hỗ trợ | `/quan-ly` → Cập nhật dữ liệu |
| Nạp / thay Excel | Upload 5 file → Nạp |
| Giọng bot, regex chủ đề | `/quan-ly` → Cách bot trả lời |
| Form chuyển cán bộ | `handoff_form_url` + đầu mối File 01 |
| Ai là admin | `admins` trong yaml + `@uel.edu.vn` |
| Backup | volume `mongo_data`, `qdrant_data` + `chatbot-data/` |

Người hỏi: domain phòng → Google → chọn mảng → hỏi.

---

## 6. Không mang từ starter

| Starter (demo) | Phòng |
|---|---|
| Khảo thí / CĐR / seed Excel | `modules: []` |
| Regex `khao_khi.*` | `routing_regex: []` |
| Email demo + `allow_non_uel_admin` | Phòng tự điền `admins` |
| Compose mount code, Qdrant `:6335` | `docker-compose.prod.yml` |

Tên phòng lúc chạy: `GET /api/auth/config` (yaml), không phải JSON bake-in.

Bảo vệ API (Origin, cookie): [api.md](api.md).

---

## 7. Checklist dán máy phòng

```text
Phòng: _____________   Domain: _____________   DEPARTMENT_ID: _____________

[ ] Copy starter mới nhất (không seed Khảo thí)
[ ] .env: JWT_SECRET, GOOGLE_CLIENT_ID, LLM_API_KEY, COOKIE_SECURE=true
[ ] yaml: id / name / domain / admins / form
[ ] modules: [] — admin tạo trên UI
[ ] DNS + HTTPS
[ ] docker compose -f docker-compose.prod.yml up -d --build
[ ] /health/ready = ok
[ ] Login admin → nạp 5 Excel → chat FAQ + RAG
[ ] Header đúng tên phòng; member không vào /quan-ly
[ ] Backup volume + chatbot-data
```

Ngoài plan: khóa đuôi mail lúc hỏi, SSO, ticket, sảnh 8 link.
