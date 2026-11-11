# Chatbot các phòng UEL (khung GitHub + RAG Khảo khí)

Nguồn khung FE/BE: [github.com/Vinhtheripper/chatbot_uel](https://github.com/Vinhtheripper/chatbot_uel) — copy trong `frontend/`. Khi lệch hợp đồng (SSE, phòng, stub), **sửa phía GitHub**, không đụng graph RAG đã chạy ổn.

PoC này **không production-ready**. Chỉ ĐBCL / Khảo khí nối RAG; năm phòng còn lại là FE + BFF mô phỏng.

## Kiến trúc

```text
Trình duyệt
    │
    ▼
Sảnh lounge :5170          (nút từng phòng)
    │
    ├── ĐBCL  :5173  ──►  BFF :30957  ──►  RAG :8000  (LangGraph + Qdrant)
    ├── QTTS  :5174  ──►  BFF :30957  ──►  stub (catalog GitHub)
    ├── PĐT   :5175  ──►  BFF :30957  ──►  stub
    ├── PNS   :5176  ──►  BFF :30957  ──►  stub
    ├── HC    :5177  ──►  BFF :30957  ──►  stub
    └── CTSV  :5178  ──►  BFF :30957  ──►  stub
```

| Lớp | Cổng | Việc làm |
|---|---|---|
| Sảnh | 5170 | Trang tĩnh, bấm phòng thì mở FE tương ứng |
| FE ĐBCL | 5173 | Chat Khảo khí |
| FE QTTS | 5174 | Chat mô phỏng Quản trị tài sản |
| FE PĐT | 5175 | Chat mô phỏng Đào tạo |
| FE PNS | 5176 | Chat mô phỏng Nhân sự |
| FE HC | 5177 | Chat mô phỏng Hành chính |
| FE CTSV | 5178 | Chat mô phỏng Công tác sinh viên |
| BFF GitHub | 30957 | `/api/chat/stream`, Bearer / `X-Department-ID` |
| RAG UEL-Innovation | 8000 | `POST /v1/chat/stream`, `X-API-Key` |

Ánh xạ RAG (duy nhất):

| FE `X-Department-ID` | Mode | Tenant RAG | Mô-đun |
|---|---|---|---|
| `dbcl` | `module_1` (Khảo khí) | `bao_dam_chat_luong` | `khao_khi` |

Mọi tổ hợp khác (ĐBCL chủ đề 2–4, năm phòng còn lại) **không gọi graph**. BFF trả lời stub từ `chatbot-api/app/data/departments.json`.

Vite proxy `/api` → `http://127.0.0.1:30957`. Hai package Python đều tên `app`: **không** `pip install` BFF vào venv RAG.

## Chạy demo (Windows)

Cần: Docker Desktop, Python 3.11+, Node.js 18+, file `.env` RAG ở gốc repo (có `APP_API_KEY`).

### 1. Bật RAG

```powershell
cd D:\ITAC\UEL-Innovation
docker compose up -d
curl.exe -fsS http://127.0.0.1:8000/health/ready
```

Nếu chưa từng nạp dữ liệu Khảo khí, xem `HUONG_DAN_ONBOARDING.md` và `HDSD_QUAN_LY_BOT.md` (trang `/admin`).

### 2. Bật sảnh + 6 FE + BFF

```powershell
cd D:\ITAC\UEL-Innovation\frontend
.\run-cluster.ps1
```

Script sẽ:

- `npm install` từng FE nếu chưa có `node_modules/vite`
- ghi `.env.local` (dev: tắt login, FE nói chuyện với BFF)
- mở cửa sổ: BFF, lounge, 6 Vite

Mở **http://127.0.0.1:5170** rồi chọn phòng.

Lần đầu năm FE ngoài ĐBCL có thể mất vài phút vì `npm install`. Nếu cửa sổ báo `'vite' is not recognized`, trong thư mục FE đó chạy `npm install` rồi `npm run dev`.

### 3. Chỉ một phần

| Mục đích | Lệnh |
|---|---|
| Chỉ BFF | `cd frontend` rồi `.\run-bff.ps1` |
| Chỉ FE ĐBCL | `.\run-fe.ps1` (cần BFF đang chạy) |
| Chỉ sảnh | `.\run-lounge.ps1` |
| Một FE khác, ví dụ CTSV | `cd frontend\chatbot-CTSV` rồi `npm install` (lần đầu) và `npm run dev` |

`run-bff.ps1` tự ghi `frontend/chatbot-api/.env`: SQLite, `CHATBOT_AUTH_DISABLED=true`, `CHATBOT_PROVIDER=rag`, `CHATBOT_RAG_API_KEY` lấy từ `APP_API_KEY` của file `.env` RAG. Không in key ra màn hình.

## Kiểm tra nhanh

| URL | Kỳ vọng |
|---|---|
| http://127.0.0.1:5170 | 6 nút phòng |
| http://127.0.0.1:5173 | Chat ĐBCL; hỏi phúc khảo / “sau đại học” ra RAG |
| http://127.0.0.1:5178 | Chat CTSV; câu trả lời có `[Phản hồi mô phỏng]` |
| http://127.0.0.1:8000/health/ready | `"status": "ready"` |
| http://127.0.0.1:30957/health/ready | BFF sẵn sàng |
| http://127.0.0.1:8000/admin | Cấu hình bot RAG (`X-Admin-Key`) |
| http://127.0.0.1:8000/ | Web chat tối thiểu RAG |

Test BFF (venv riêng, không trộn với `.venv` RAG):

```powershell
cd D:\ITAC\UEL-Innovation\frontend\chatbot-api
.\.venv\Scripts\python.exe -m pytest -q
```

## Biến môi trường FE (`.env.local`)

```
VITE_API_URL=/api
VITE_MOCK_API=false
API_PROXY_TARGET=http://127.0.0.1:30957
VITE_SHOW_SOURCES=true
VITE_AUTH_DISABLED=true
```

| Biến | Ý nghĩa |
|---|---|
| `VITE_MOCK_API=false` | Gọi BFF thật. `true` hoặc bỏ trống trong dev → mock trong trình duyệt, **không** qua BFF |
| `VITE_AUTH_DISABLED=true` | Bỏ trang đăng nhập (dev). BFF cũng cần `CHATBOT_AUTH_DISABLED=true` |
| `VITE_SHOW_SOURCES` | ĐBCL: `true` (chỉ hiện dòng nguồn nếu câu trả lời chưa có `Nguồn:`). Phòng stub: `false` |

Mỗi FE gửi `X-Department-ID` theo `src/config/department.json` (`dbcl`, `qtts`, `pdt`, `pns`, `hc`, `ctsv`).

## Hội thoại (ĐBCL / RAG)

FE giữ `conversation_id` sau lượt đầu. BFF chuyển id đó sang RAG. Câu ngắn như “sau đại học” / “ĐHCQ” được ghép vào câu hỏi trước (ví dụ thời hạn phúc khảo) rồi mới truy xuất.

Restart API RAG hoặc nhiều worker Docker sẽ **mất** bộ nhớ hội thoại trong process — bắt đầu chat mới.

## Cấu trúc thư mục

```text
frontend/
├── lounge/                 sảnh :5170
├── chatbot-DBCL/           FE ĐBCL
├── chatbot-qtts/
├── chatbot-PDT/
├── chatbot-PNS/
├── chatbot-HC/
├── chatbot-CTSV/
├── chatbot-api/            BFF FastAPI :30957
├── run-cluster.ps1
├── run-bff.ps1
├── run-fe.ps1              chỉ ĐBCL :5173
└── run-lounge.ps1
```

## Sự cố thường gặp

| Hiện tượng | Cách xử |
|---|---|
| `'vite' is not recognized` | `cd` đúng thư mục FE, `npm install`, rồi `npm run dev` |
| ĐBCL hỏi mãi “cho biết hệ đào tạo” | RAG chưa restart sau khi sửa follow-up; `docker compose restart api` |
| ĐBCL lỗi 502 / key | `.env` RAG có `APP_API_KEY`; chạy lại `run-bff.ps1` (script copy key, không in ra) |
| Phòng khác trả “chưa gắn mô-đun RAG” | BFF cũ; restart cửa sổ BFF (`run-bff.ps1`) để fallback stub |
| Cổng đã dùng | Đóng cửa sổ Vite/BFF cũ hoặc đổi port trong `vite.config.js` |
| Login hiện ra | `.env.local` thiếu `VITE_AUTH_DISABLED=true` — `run-cluster.ps1` ghi lại file này |

## Không làm

- Không `pip install` package BFF vào `.venv` RAG (cả hai đều tên `app`).
- Không sửa graph/Qdrant chỉ để nối FE GitHub.
- Không coi năm phòng stub là chatbot nghiệp vụ đã nạp dữ liệu.
- Không commit `.env`, `.env.local`, hay API key.
