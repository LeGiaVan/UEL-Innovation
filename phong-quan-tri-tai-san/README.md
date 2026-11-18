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
# terminal 1
cd chatbot-api && pip install -e . && uvicorn app.main:app --reload --port 8000
# terminal 2
cd chatbot-web && npm install && npm run dev
```

Compose (P6): `docker compose up -d --build` — 1 app + mongo + qdrant. Không Postgres, không MinIO.

Không làm trong starter: ticket, inbox, Holland/MBTI/BSKT, `RAG_ROUTES`, login mật khẩu.
