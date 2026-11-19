# Phòng Tuyển sinh & Công tác sinh viên

`DEPARTMENT_ID=ctsv` · `ctsv.chat.uel.edu.vn`

Điền `.env` + `chatbot-api/configs/department.yaml` (admins, form), rồi:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Hướng dẫn: `docs/deploy.md` (gốc repo).
