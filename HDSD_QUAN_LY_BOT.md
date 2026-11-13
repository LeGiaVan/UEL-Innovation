# Hướng dẫn sử dụng — quản lý bot theo phòng / mô-đun

Tài liệu này dành cho người vận hành sau khi đã nạp dữ liệu (3 template → MinIO / PostgreSQL / Qdrant). **Không sửa mã Python** khi thêm phòng mới nếu workbook đúng schema. Routing nghiệp vụ nằm trong Template 1; phần dưới đây là **cách bot nói** và **tham số runtime**.

Giao diện: http://127.0.0.1:8000/admin  
Chat người học: http://127.0.0.1:8000/  
API: http://127.0.0.1:8000/docs  

Trang `/admin` gửi header `X-Admin-Key`. Giá trị đúng là **`APP_ADMIN_API_KEY`** trong `.env` (không phải tên biến). Bản `development` cũng nhận **`APP_API_KEY`**. Sửa `.env` xong recreate container, không cần build: `docker compose up -d --no-build --force-recreate api`.

## 1. Ai quản lý cái gì

| Việc | Nơi cấu hình | Ghi chú |
|---|---|---|
| Phạm vi trả lời / cần cán bộ / ngoài phạm vi | Template 1 (Excel) → sync | Classifier chỉ chọn `rule_id` đã duyệt |
| FAQ | Template 2 | Khớp câu đã chuẩn hóa |
| Tài liệu RAG | Template 3 → Qdrant | Chat không đọc Excel lúc hỏi |
| Vai trò, ràng buộc, thuật ngữ, cách viết, metadata | Prompt pack (trang `/admin` hoặc API) | Overlay, không đè lớp an toàn |
| Alias câu hỏi exact (bỏ LLM) | `routing_aliases` trên pack | Key = `rule_id` trong Template 1 |
| `top_k`, `score_threshold`, `mode`, `faq_boost` | YAML mô-đun / `/admin` | Trống = `.env` `RAG_TOP_K`, `RAG_SCORE_THRESHOLD`, `RAG_SEARCH_MODE`, `GOLD_FAQ_SCORE_BOOST` |
| Profile `generic` / `assessment` | YAML / `/admin` | Phòng mới: `generic`. `assessment` chỉ Khảo khí |
| API key chat người học | `.env` → `API_CLIENTS` | Không lưu trên `/admin` |
| Lounge FE → tenant RAG | BFF `.env` `CHATBOT_RAG_ROUTES` | Overlay; `dbcl`/`khao_khi` giữ mặc định |

**Không** đưa toàn bộ system prompt tự do. Lớp cứng luôn giữ: chỉ dùng evidence, không bịa, không lộ secret, cô lập tenant. Mã nguồn gắn metadata/API; câu trả lời người học không nhồi citation hay `gold:`.

## 2. Phòng mới — trình tự

Trên http://127.0.0.1:8000/admin tab **Thêm mô-đun** (không cần Swagger):

1. Copy 3 file `template/`, điền Excel. Tên mô-đun trong Template 1 phải khớp form.
2. Dán Admin key. Chọn **Phòng mới** hoặc **Thêm mô-đun vào phòng có sẵn**.
3. Kéo thả 3 Excel → **Kiểm tra template** → **Nạp thử** rồi **Nạp đầy đủ** (Bronze → Silver → Gold).
4. Tab **Cấu hình bot** → pack → **Lưu**. Tab **Thử chat** (không cần `API_CLIENTS`).
5. Cấp key chat trong `.env` (`API_CLIENTS`) rồi recreate API khi người học dùng `/`.

Chi tiết API: `HUONG_DAN_ONBOARDING.md`.

Volume Docker `api_config` gắn `/app/configs`: file `configs/departments.yaml` trong git **không** tự ghi vào container đang chạy. Sửa pack bằng `/admin` hoặc API.

## 3. Prompt pack

- **Vai trò**: 1–2 câu, tối đa 500 ký tự.  
- **Ràng buộc**: bullet phòng duyệt (cấm diễn giải, giữ số ngày…), tối đa 4000.  
- **Thuật ngữ**: mỗi dòng `KEY = nghĩa`. Tối đa 20 cặp. Ví dụ Khảo khí:

```
ĐHCQ = đại học chính quy
SĐH = sau đại học
VB2/VLVH = văn bằng 2 / vừa làm vừa học
```

Module `generic` **không** nhận sẵn ĐHCQ/SĐH. Chỉ điền glossary nếu nghiệp vụ cần.

- **Cách viết (`answer_style`)**: ghi chú đưa vào user prompt lúc generate (tối đa 2000). Ví dụ Khảo khí: trả lời từng hệ thành mục riêng. Phòng khác để trống.
- **Prompt metadata (`metadata_system`)**: system text khi cần LLM gắn hệ đào tạo/chủ đề. Để trống = không gọi bước này (trừ `profile=assessment` khi chưa điền, lúc đó mới dùng skeleton trong code).
- **Câu chào / ngoài phạm vi / làm rõ**: để trống thì dùng câu mặc định theo tên mô-đun. Khảo khí nên điền đủ ba câu trong pack, không dựa vào `prompts.py`.  
- **routing_aliases**: JSON `{"RULE_ID": ["câu khớp nguyên văn", ...]}`.  
- **top_k**, **score_threshold**, **mode** (`hybrid`/`dense`), **faq_boost**: số/mode; để trống ghi mặc định `.env`.

Lưu dùng `If-Match` (ETag). Nếu 409: tải lại rồi lưu.

## 4. Thử chat

`POST /v1/admin/chat-preview` với Admin key:

```json
{
  "department_id": "phong_dao_tao",
  "module_code": "dang_ky_hoc_phan",
  "message": "Thời hạn đăng ký học phần?"
}
```

Response có `status`, `rule_id`, `routing_source`, `citations`, `answer`. Dùng để kiểm pack + Template 1 trước khi cấp key người học.

## 5. API

| Method | Đường dẫn | Việc |
|---|---|---|
| GET | `/v1/admin/tenants` | List mô-đun, `has_prompt_pack` |
| GET | `/v1/admin/modules/{dept}/{mod}/bot` | Đọc pack, header `ETag` |
| PUT | `/v1/admin/modules/{dept}/{mod}/bot` | Ghi pack, header `If-Match` |
| POST | `/v1/admin/chat-preview` | Thử agent |

Header mọi lệnh: `X-Admin-Key`. PUT body:

```json
{
  "profile": "generic",
  "prompt_pack": {
    "role": "Trợ lý Phòng Đào tạo",
    "constraints": "Không bịa mã học phần.",
    "glossary": {},
    "answer_style": "",
    "metadata_system": ""
  },
  "messages": {
    "greeting": "",
    "out_of_scope": "",
    "clarification": ""
  },
  "retrieval": { "top_k": 5, "score_threshold": 0.4167, "mode": "hybrid", "faq_boost": 0.12 },
  "routing_aliases": {}
}
```

Nạp release mới **không xóa** pack đã lưu (chỉ cập nhật tên, nguồn, profile, contact).

## 6. Việc vẫn nằm trong code (không có trên UI)

Phòng / mô-đun mới: Template 1–3 + YAML pack (`generic`) + `.env` (`API_CLIENTS`, retrieval mặc định). Không sửa Python.

Vẫn trong code có chủ đích:

- Lớp an toàn generate (`GENERATE_FOUNDATION`), chống injection, kiểm citation, fail-closed khi thiếu rule  
- Hybrid RRF, Cosine, prefetch; FAQ exact sau `normalize_question`  
- Extension `profile=assessment` (Khảo khí: ĐHCQ/SĐH, điểm I, TL03/TL04, rewrite phúc khảo). `legacy_mode` chỉ test  
- Secret `API_CLIENTS` / `APP_ADMIN_API_KEY`

`generic` không chạy heuristic khảo thí, không rewrite “Portal UEL”, không dùng câu chào Khảo khí. Pack trống → chào/OOS theo tên mô-đun trong YAML.

## 7. Lỗi thường gặp

| Hiện tượng | Việc kiểm |
|---|---|
| Admin 401 | Sai/thiếu `APP_ADMIN_API_KEY`, chưa recreate API |
| 409 khi lưu | ETag cũ; Tải cấu hình bot rồi lưu lại |
| 404 module | Chưa ingest / sai `department_id`/`module_code` |
| Chat `/` 403 | Chưa cấp `API_CLIENTS`; thử `/admin` preview trước |
| Pack trong git không thấy trên Docker | Volume `api_config`; sửa qua `/admin` |
| Bot vẫn nói ĐHCQ dù phòng mới | Pack phòng đó còn glossary; xóa glossary generic |
