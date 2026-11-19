# chatbot-web — giao diện chatbot phòng

React 18 + Vite 5. Tên phòng lúc chạy lấy từ `GET /api/auth/config` (yaml), không bake ĐBCL hay một mô-đun.

## Dev

API mặc định `http://127.0.0.1:8001` (xem `.env.example`). Cookie phiên `uel_session`; không gửi `X-Department-ID`.

```bash
cp .env.example .env.local
npm install
API_PROXY_TARGET=http://127.0.0.1:8001 npm run dev
```

Mở `http://localhost:5173`. Google origin cần gồm cổng này.

## Production

Build vào image: `docker compose -f docker-compose.prod.yml up -d --build` ở thư mục phòng. FastAPI phục vụ `dist` cùng origin `:8000`.

Không đặt secret vào biến `VITE_*`.
