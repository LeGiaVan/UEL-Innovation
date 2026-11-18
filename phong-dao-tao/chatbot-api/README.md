# chatbot-api

FastAPI một process: HTTP + (P4) RAG + (P3) ingest. Không Postgres, không MinIO, không `RAG_ROUTES`.

```bash
cd chatbot-api
cp .env.example .env
pip install -e .
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`DEPARTMENT_ID` lấy từ `.env`. Client không gửi mã phòng.
