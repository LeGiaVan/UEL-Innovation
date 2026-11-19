# Phòng Khoa học công nghệ

`DEPARTMENT_ID=khcn` · `khcn.chat.uel.edu.vn`

Điền `.env` + `chatbot-api/configs/department.yaml` (admins, form), rồi:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Hướng dẫn: `docs/deploy.md` (gốc repo).
