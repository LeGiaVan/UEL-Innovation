# Build từ thư mục chatbot hiện tại: docker build -t chatbot .
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json /app/chatbot-web/
WORKDIR /app/chatbot-web
RUN npm ci

COPY . /app/chatbot-web


# Build-time env cho Vite (baked vào bundle — đổi giá trị phải rebuild).
ARG VITE_MOCK_API=false
ENV VITE_MOCK_API=$VITE_MOCK_API
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ─── Stage 2: serve qua nginx ───────────────────────────────
FROM nginx:1.27-alpine AS runtime

# wget dùng cho healthcheck (đã có trong base image)
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/chatbot-web/dist /usr/share/nginx/html

# Tắt logging server tokens
RUN sed -i 's/# server_tokens off;/server_tokens off;/' /etc/nginx/nginx.conf || true

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=5 --start-period=10s \
  CMD wget -qO- http://localhost/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
