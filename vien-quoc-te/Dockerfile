FROM node:20-alpine AS ui
WORKDIR /web
COPY chatbot-web/package.json chatbot-web/package-lock.json* ./
RUN npm install
COPY chatbot-web/ ./
RUN npm run build

FROM python:3.12-slim AS app
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY chatbot-api/pyproject.toml ./
COPY chatbot-api/app ./app
COPY chatbot-api/configs ./configs
RUN pip install --no-cache-dir .
COPY --from=ui /web/dist ./ui_dist
ENV UI_DIST_DIR=/app/ui_dist
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
