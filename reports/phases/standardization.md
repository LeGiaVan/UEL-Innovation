# Chuẩn hóa Template 1 / multi-tenant — kết quả thực tế

Cập nhật: 2026-11-11. Không tuyên bố production-ready hay hoàn tất toàn bộ `docs/plan-multi-tenant-routing.md`.

## Vận hành được bằng API/config

- Registry: `configs/departments.yaml` (nguồn duy nhất). Admin `GET/PUT /v1/admin/registry` với ETag, `POST /v1/admin/sources`, `POST /v1/admin/sync` (dry-run mặc định).
- Chat: service key gắn tenant + danh sách module; `POST /v1/chat` nhận `module_code`; `GET /v1/modules` liệt kê module được cấp. Tenant không do client gửi.
- Runtime production đọc rule Template 1 từ Silver theo tenant/module/release; exact topic/alias rồi classifier theo ID có thật. Thiếu rule / ID bịa / classifier lỗi → hỏi rõ hoặc handoff, không retrieval.
- Profile `generic` mặc định; `assessment` là extension Khảo khí. `bot_behavior` chỉ đưa vào classifier, chưa phải DSL workflow.

## Kiểm thử lần này

| Bộ | Kết quả |
|---|---|
| Unit + health | 94 passed |
| Browser smoke (Chrome, mock `/v1/modules` + chat) | 1 passed |
| Mypy (`citation`, `policy`, `auth`, `admin`, `chat`, `--follow-imports=silent`) | pass |
| Ruff các file vừa sửa | pass |
| PostgreSQL integration trên `uel_rag_test_standardization_20261111` | 6 passed (`-m integration`, gồm onboarding Finance/payments) |
| Groq Template 1 smoke | `reports/phases/standardization-routing-smoke.json` |

Ba câu smoke Groq:

1. Ngoài phạm vi → `out_of_scope`, không search/generate, contact theo rule.
2. Khiếu nại cá nhân → `human_handoff`, không search/generate.
3. Xin điểm I → routing `answer_allowed` đúng rule Template 1; generate chạy; citation LLM không khớp nên **trả extractive từ Gold đã duyệt** (`status=answered`). Không tính generation thành công. Trước đó nhánh này là `insufficient_evidence`.

Gold 130 chunks (release_id) không rebuild lại trong lượt này.

## Image / runtime

- Image mới: `uel-rag-poc-api:standardization` (`sha256:ffe6506e54f6c7aeed5bb54370effd6f19a1f554c3ec1107390b1f01d45095ae`).
- Container thử cổng 18080: `/health/live` 200, `/health/ready` postgres/qdrant/minio ok, `/v1/modules` 401 không key / 200 có key (`khao_khi`), admin không key 401, `module_code` không được cấp 403. Đã gỡ container thử.
- Container chính `uel-rag-poc-api-1` vẫn image cũ `sha256:db31e91062ed…`, không restart/deploy.

## Còn thiếu so với plan

Database registry, job API, activation/rollback nguyên tử nhiều kho, end-user identity/BFF, durable shared checkpoint, operator audit, workflow `bot_behavior` tùy ý, UAT trên 17 rule + paraphrase. Phase 8 KPI vẫn IN_PROGRESS. Groq miễn phí có thể 429; fail-closed, không coi quota lỗi là đạt accuracy.
