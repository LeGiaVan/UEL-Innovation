FROM python:3.14-slim
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && useradd --create-home --uid 10001 chatbot
COPY app ./app
RUN mkdir -p /app/data && chown -R chatbot:chatbot /app/data
USER chatbot
EXPOSE 30957
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:30957/health/ready')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "30957", "--no-proxy-headers", "--no-access-log"]
