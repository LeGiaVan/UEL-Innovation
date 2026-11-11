FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app app

COPY pyproject.toml README.md ./
RUN python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch
RUN python -m pip install --no-cache-dir "FlagEmbedding>=1.3,<2"

COPY app ./app
COPY --chown=app:app configs ./configs
RUN python -m pip install --no-cache-dir .

ENV HF_HOME=/tmp/huggingface
RUN mkdir -p /app/data /app/reports /tmp/huggingface \
    && chown -R app:app /app/configs /app/data /app/reports /tmp/huggingface

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
