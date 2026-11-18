# Starter — một đơn vị UEL

Copy thư mục này thành `phong-*/` hoặc `vien-quoc-te/`. Dev phòng sửa code trong bản copy. Bug chung vá ở `starter/`, phòng tự merge.

```text
starter/
  chatbot-web/     # React
  chatbot-api/     # FastAPI
  chatbot-data/    # 5 Excel + release
  Dockerfile
  docker-compose.yml
```

Dev nhanh:

```bash
# Mongo (dev local uvicorn, không đợi P6)
docker compose up -d mongo

# terminal 1 — nếu :8000 bị chiếm thì dùng 8001 + API_PROXY_TARGET
cd chatbot-api && pip install -e . && uvicorn app.main:app --reload --port 8001
# terminal 2
cd chatbot-web && npm install && npm run dev
```

Compose (P6): `docker compose up -d --build` — 1 app + mongo + qdrant. Không Postgres, không MinIO.

Không làm trong starter: ticket, inbox, Holland/MBTI/BSKT, `RAG_ROUTES`, login mật khẩu.
