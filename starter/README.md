# Starter — một đơn vị UEL

Bản **demo**. Dữ liệu Khảo thí / Chuẩn đầu ra chỉ để thử. Deploy phòng thật: `docs/deploy.md`. Copy phòng **không** mang mô-đun demo.

Copy nguyên thư mục này thành `phong-*/` hoặc `vien-quoc-te/`. Điền cấu hình, nạp 5 Excel, chạy Compose. Không sửa code rồi mới lên được.

```text
starter/                 # hoặc thư mục phòng sau khi copy
  chatbot-web/           # React (build vào image)
  chatbot-api/           # FastAPI + RAG
  chatbot-api/configs/   # department.yaml, persona.yaml
  chatbot-data/          # 5 Excel 3.0 + seed
  Dockerfile
  docker-compose.yml         # demo (mount code, mở Qdrant :6335)
  docker-compose.prod.yml    # máy phòng
  .env.example
```

## Clone rồi chạy (production)

1. Copy `starter/` thành thư mục phòng (`python scripts/clone_starter.py`). Không mang seed Khảo thí.
2. `cp .env.example .env` rồi điền:
   - `DEPARTMENT_ID`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`
   - `LLM_API_KEY` (Anthropic Haiku)
   - `EMBED_BACKEND=bge-m3` (đã sẵn trong example; Compose khóa lại)
3. Sửa `chatbot-api/configs/department.yaml`: `id`, `name`, `domain`, `admins` (`@uel.edu.vn`), `handoff_form_url`. Không bật `allow_non_uel_admin` trên máy phòng.
4. Cán bộ nạp 5 Excel 3.0 trên `/quan-ly` (không copy seed demo).
5. Google Cloud: origin = domain phòng **và** `http://localhost:8000` (Compose) / `http://localhost:5173` (dev).
6. Chạy trên máy phòng:

```bash
cd <thu-muc-phong>
docker compose -f docker-compose.prod.yml up -d --build
```

Demo local: `docker compose up -d --build` (file `docker-compose.yml`).

Mở `http://localhost:8000` (hoặc domain phòng). Đăng nhập Google → admin `@uel.edu.vn` có trong yaml vào `/quan-ly` nạp 5 file → người hỏi chat.

Lần đầu image tải BGE-M3 (CPU, dim 1024) trong lúc `docker compose build`. Nạp lại Excel sau khi khóa BGE — đừng trộn vector hash.

```bash
docker compose exec app python scripts/ingest_seed.py   # chỉ starter, khi còn seed Khảo thí
docker compose exec app python scripts/measure_p6.py     # p95 sau warmup
```

Mongo trong Compose không publish ra máy (tránh đụng Mongo dev `:27017`). App nói `mongodb://mongo:27017` trong mạng Compose. Cổng host demo: `8000` (app), `6335` (Qdrant). File prod **không** mở Qdrant. Dev uvicorn: `docker compose up -d mongo qdrant` rồi thêm `ports: ["27017:27017"]` nếu cần Mongo trên localhost.

Backup: volume Compose `mongo_data` và `qdrant_data`.

## Dev nhanh (không đợi image)

```bash
cp .env.example .env
docker compose up -d mongo qdrant
# terminal 1
cd chatbot-api && pip install -e ".[dev]" && uvicorn app.main:app --reload --port 8001
# terminal 2 — API_PROXY_TARGET nếu API không ở :8000
cd chatbot-web && npm install && API_PROXY_TARGET=http://127.0.0.1:8001 npm run dev
```

Pytest (hash, không tải BGE):

```bash
cd chatbot-api && pip install -e ".[dev]" && pytest
```

BGE-M3 chỉ production / Compose. Hash chỉ test.

Không làm trong starter: ticket, inbox, Holland/MBTI/BSKT, login mật khẩu, Postgres, MinIO.
