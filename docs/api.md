# Bảo vệ API

POST/PUT/DELETE `/api` cần Origin (hoặc Referer) trong allowlist — curl/Postman mặc định **403**. Chat/admin cần cookie Google. `/docs` tắt. `GET /api/modules` cần login.

Người đã login **và** giả đúng Origin vẫn gọi tool được. Tem Origin chặn gọi đại, không chặn chiếm phiên.

Deploy: [deploy.md](deploy.md).

---

## Hai lớp

```text
Trình duyệt (tự gửi Origin)     curl không Origin
        │                              │
        ▼                              ▼
   Origin ∈ allowlist              403 Origin không hợp lệ
        │
   cookie uel_session?
        │
   chưa login → 401
   member     → chat
   admin yaml → chat + /api/admin
```

Code: `starter/chatbot-api/app/core/origins.py`, `middleware.py`, `factory.py`.

---

## Origin

Allowlist (không hard-code 8 phòng):

- `http://localhost:8000` / `127.0.0.1:8000`
- `http://localhost:5173` / `127.0.0.1:5173` (Vite)
- `https://{domain}` từ `department.yaml`
- `http://{domain}` khi `COOKIE_SECURE=false`
- CSV `CORS_ORIGINS`

Cùng list cho CORS. GET `/health/*` không cần Origin.

---

## Phiên

Google ID token → cookie HttpOnly `uel_session` (SameSite=Lax). Role: có trong `admins` yaml **và** `@uel.edu.vn` (starter demo có thể `allow_non_uel_admin: true`). Client không đổi `department_id` / `role`.

---

## Endpoint

| Endpoint | Origin | Auth |
|---|---|---|
| `GET /health/*` | không | công khai |
| `GET /api/auth/config`, `/me` | không | cookie tùy chọn |
| `POST /api/auth/google`, `/logout` | có | ID token / cookie |
| `GET /api/modules` | không | login |
| `POST /api/chat/stream` | có | login + hạn mức |
| `/api/admin` GET | không | admin |
| `/api/admin` POST/PUT | có | admin |
| `/docs` | — | 404 mặc định |

Giả Origin đúng + cookie → vẫn gọi được. Site lạ → 403.
