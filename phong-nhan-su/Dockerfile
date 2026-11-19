FROM node:20-alpine AS ui
WORKDIR /web
COPY chatbot-web/package.json chatbot-web/package-lock.json ./
RUN npm ci
COPY chatbot-web/ ./
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM python:3.12-slim AS app
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV HF_HOME=/opt/hf TRANSFORMERS_CACHE=/opt/hf HF_HUB_DISABLE_TELEMETRY=1
ENV EMBED_BACKEND=bge-m3
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY chatbot-api/pyproject.toml ./
COPY chatbot-api/app ./app
COPY chatbot-api/configs ./configs
COPY chatbot-api/scripts ./scripts
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir ".[embed]" \
    && python -c "from FlagEmbedding import BGEM3FlagModel; BGEM3FlagModel('BAAI/bge-m3', use_fp16=False, devices='cpu')"
COPY --from=ui /web/dist ./ui_dist
ENV UI_DIST_DIR=/app/ui_dist
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=8 --start-period=90s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
