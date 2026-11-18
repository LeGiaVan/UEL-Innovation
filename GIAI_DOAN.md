# Kế hoạch thực hiện theo giai đoạn

Tài liệu này dùng để **làm việc**, không thay `PLAN_UPDATE.md`.

| Vai trò | File |
|---|---|
| Đặc tả đã khóa (schema Excel, auth, routing, repo) | `PLAN_UPDATE.md` |
| Thứ tự làm, checklist, cửa ra từng pha | **file này** |
| Cấu trúc 8 thư mục đơn vị | `cautruc8duan.md` + mục 5 `PLAN_UPDATE.md` |
| Báo cáo sau mỗi pha | `bao-cao-giai-doan/` |

**Cách làm:** xong một pha → ghi `bao-cao-giai-doan/P<n>.md` → chỉ sang pha sau khi cửa ra đạt. Không nhảy pha. Không code ngoài phạm vi pha đang mở.

Trạng thái: `NOT_STARTED` | `IN_PROGRESS` | `BLOCKED` | `READY_FOR_REVIEW` | `ACCEPTED`

---

## Hiện trạng

| Pha | Tên | Trạng thái |
|---|---|---|
| P0 | Nền `starter/` + 1 UI + vỏ 8 phòng | `READY_FOR_REVIEW` |
| P1 | Google ID token + JWT cookie | `ACCEPTED` |
| P2 | Hạn mức hỏi | `ACCEPTED` |
| P3 | Ingest 5 Excel 3.0 → disk + Mongo + Qdrant | `ACCEPTED` |
| P4 | Routing 4 tầng + RAG + Form | `ACCEPTED` |
| P5 | Hai màn admin | `READY_FOR_REVIEW` |
| P6 | Chốt starter: Docker + đo chất lượng / độ trễ | `NOT_STARTED` |
| P7 | Clone starter — phòng deploy ngay | `NOT_STARTED` |

Bước hiện tại (2026-11-18): **P5 `READY_FOR_REVIEW`**. P4 `ACCEPTED`. Embed: BGE-M3 dense 1024 (không sparse). Chờ nghiệm thu P5 rồi P6 (chốt `starter/`) trước khi clone P7.

---

## Quy tắc chung (mọi pha)

Đọc mục 1 và mục 14 của `PLAN_UPDATE.md` trước khi sửa code.

- Một phòng = một thư mục + một Compose + Mongo riêng + Qdrant riêng + một domain.
- Clone phòng **chỉ sau P6 ACCEPTED** trên `starter/`. P7 không vá bug starter.
- Production: **một** container `app` (build `chatbot-web` → FastAPI phục vụ `dist`) + mongo + qdrant.
- Không Postgres, không MinIO bắt buộc, không ticket/inbox, không login mật khẩu, không API key `/admin`.
- Template 3.0 **không đổi cột/sheet** (file đã gửi phòng).
- `DEPARTMENT_ID` từ `.env`; không tin `role` / mã phòng từ trình duyệt.
- LLM = API; BGE-M3 = trong container, CPU.
- Mỗi phòng một `GOOGLE_CLIENT_ID`.
- Mọi mô-đun `profile: generic`.
- Báo cáo không chứa secret, API key, cookie, dữ liệu cá nhân.

---

## P0 — Nền `starter/` + một UI + vỏ 8 phòng

**Báo cáo:** `bao-cao-giai-doan/P0.md`

### Làm

1. Tạo `starter/` đúng cây mục 5 `PLAN_UPDATE.md`: `chatbot-web/`, `chatbot-api/`, `chatbot-data/`, `Dockerfile`, `docker-compose.yml`, `README.md`.
2. Gộp **một** UI trong `starter/chatbot-web` (React 18, Vite 5, RTK + Thunk). Xóa hướng ticket, inbox, Holland/MBTI/BSKT, 7 app copy.
3. `chatbot-api`: FastAPI một process; bỏ phụ thuộc Postgres/MinIO trên đường chạy mới; bỏ `RAG_ROUTES` hard-code.
4. Tạo **8 thư mục đơn vị** (copy skeleton từ starter: layout + yaml mẫu, chưa cần chat chạy):
   - `phong-hanh-chinh/` (`hc`)
   - `phong-tuyen-sinh-cong-tac-sinh-vien/` (`ctsv`)
   - `phong-dao-tao/` (`pdt`)
   - `phong-quan-tri-tai-san/` (`qtts`)
   - `vien-quoc-te/` (`vqt`)
   - `phong-nhan-su/` (`pns`)
   - `phong-khoa-hoc-cong-nghe/` (`khcn`)
   - `phong-bao-dam-chat-luong/` (`dbcl`)
5. Mỗi phòng: `department.yaml` đúng `id` / `name` / `domain`; `modules[].profile: generic`.
6. Copy 5 file `template/` vào `starter/chatbot-data/templates/`.

### Không làm ở P0

Google login, ingest Excel, routing 4 tầng, màn admin nạp file, `docker compose up --build` nghiệm thu (để P6).

### Cửa ra

- [ ] Cây `starter/` khớp mục 5.
- [ ] 8 thư mục đơn vị tồn tại, cùng layout.
- [ ] FE starter không còn ticket / 7 copy / khảo thí ngoài phạm vi.
- [ ] Báo cáo `P0.md` ghi đường dẫn đã tạo/xóa.

---

## P1 — Google rồi JWT

**Báo cáo:** `bao-cao-giai-doan/P1.md`  
**Spec:** mục 7 `PLAN_UPDATE.md`

### Làm

1. FE: nút Google Identity Services; gửi ID token `POST /api/auth/google`.
2. BE: verify JWKS, `aud`, `exp`, `email_verified`.
3. Role: mọi Gmail đã Google = `member`. `department_admin` chỉ khi email `@uel.edu.vn` **và** có trong `admins` yaml phòng đó.
4. JWT HS256 + `sid` Mongo; cookie HttpOnly `uel_session`; TTL 8 giờ. `department_id` lấy env.
5. `GET /api/auth/me`, logout xóa cookie + thu hồi `sid`.
6. Tắt login mật khẩu. Chưa login thì không hỏi được chatbot.

### Không làm ở P1

Lọc đuôi `@st.uel` / `@uel` lúc hỏi. SSO trường. Một Client ID dùng chung 8 phòng.

### Cửa ra

- [x] Login Google trên domain (hoặc localhost) cấp cookie; request sau không gửi ID token Google.
- [x] Email không có trong `admins` không thấy `/quan-ly`.
- [x] Client không đổi được `department_id`.

---

## P2 — Hạn mức

**Báo cáo:** `bao-cao-giai-doan/P2.md`  
**Spec:** mục 8 `PLAN_UPDATE.md`

### Làm

Áp `POST /api/chat/stream` cho `member`:

| Cửa | Mặc định | HTTP |
|---|---|---|
| Số từ > 1000 | 1000 | 400 |
| Lượt / phút | 10 | 429 + `Retry-After` |
| Token LLM / ngày UTC+7 | 50 000 | 429 |

Số lấy `department.yaml`. FAQ/regex/cosine không trừ token ngày, vẫn tính 1 lượt/phút. Admin nạp/persona/thử chat không ăn hạn mức người hỏi (thử chat trần 20/phút). Mongo: `rate_windows`, `token_daily`.

### Cửa ra

- [x] Vượt từng cửa trả đúng mã.
- [x] Reset ngày 00:00 UTC+7.
- [x] Admin thử chat không trừ hạn mức `member`.

---

## P3 — Ingest 5 Excel 3.0

**Báo cáo:** `bao-cao-giai-doan/P3.md`  
**Spec:** mục 4 và 4.6 `PLAN_UPDATE.md`

### Làm

1. Parser một bộ cho 8 phòng: File 01–05, bỏ sheet `_DS` và Hướng dẫn.
2. Upload đủ 5 file / **một** `module_code`. Thiếu file = không nạp.
3. `rule_id` = `{module_code}.{slug(chủ đề)}`. Trùng slug = ERROR.
4. File 04/05 được 0 dòng (WARNING). File 01 ≥ 1 dòng chủ đề.
5. Hợp lệ: `chatbot-data/modules/<ma>/releases/<release_id>/source/` + Mongo (`routing_rules`, `faqs`, `milestones`, `releases`) + Qdrant `rules` + `docs` (`faq` / `business` / `milestone` / `intro`). File 03 quét hết B–F, không chặn theo Loại.
6. ERROR → 422, giữ release cũ. Lỗi giữa chừng: giữ bản cũ. Cắt release atomic.
7. Không lọc audience lúc hỏi. Không Postgres.
8. Dữ liệu Khảo khí ĐBCL **map sang 5 file 3.0** (điền Excel, không sửa template trống gốc).

### Cửa ra

- [x] Nạp đủ 5 file hợp lệ → chat dùng release mới.
- [x] Thiếu file / sai scope / trùng FAQ → 422, bản cũ còn.
- [x] 04/05 trống vẫn nạp.
- [x] Không ghi Postgres.

---

## P4 — Routing 4 tầng + RAG + Form

**Báo cáo:** `bao-cao-giai-doan/P4.md`  
**Spec:** mục 9 `PLAN_UPDATE.md`

### Làm

Thứ tự: chuẩn hóa câu → (1) FAQ exact File 02 → (2) regex persona → (3) cosine File 01 ≥ 0.62, không hòa → (4) LLM chỉ `rule_id` hoặc `null`.

- `answer_allowed` → RAG `docs` (faq boost 1.5 + File 03/04/05); trúng thủ tục thì hydrate đủ D+E+F cùng sheet; ưu tiên `milestone` nếu câu hạn/lịch; citation; thiếu nguồn không đoán.
- `human_handoff` / `out_of_scope` → không RAG; nút Google Form yaml + đầu mối Excel.
- Tầng 4 không RAG, không bịa quy định/ngày.
- Regex: UI chọn chủ đề (không gõ mã); `rule_id` gãy nếu đổi tên chủ đề.

### Cửa ra

- [x] FAQ khớp → nguyên văn, không LLM.
- [x] Cosine thấp / hòa → clarify, không RAG.
- [x] OOS/handoff hiện Form (khi yaml có `handoff_form_url`).
- [x] `routing_source` ∈ `faq_exact` \| `regex` \| `cosine` \| `llm` \| `llm_clarify`.

---

## P5 — Hai màn admin

**Báo cáo:** `bao-cao-giai-doan/P5.md`  
**Spec:** mục 10, 12 `PLAN_UPDATE.md`

### Làm

Chỉ `department_admin`, đường `/quan-ly`:

1. Nạp tri thức: chọn mô-đun, upload 5 Excel, hiện checksum / số dòng / WARNING, một nút nạp (không dry-run Postgres).
2. Persona: greeting, OOS, clarification, role, constraints, glossary, style, regex (dropdown chủ đề), cosine, `top_k`. Thử chat 4 tầng + `routing_source`. Không dán system prompt đè an toàn.

### Cửa ra

- [x] `member` không vào `/quan-ly`.
- [x] Nạp + sửa persona + thử chat trên UI.
- [x] Regex chọn từ danh sách File 01 đang chạy.

---

## P6 — Chốt `starter/` (Docker + chất lượng)

**Báo cáo:** `bao-cao-giai-doan/P6.md`  
**Spec:** mục 6 và 6.1 `PLAN_UPDATE.md`

Pilot chạy **trong `starter/`**, không lấy thư mục ĐBCL làm gốc. Chưa đạt cửa ra thì **không mở P7**.

### Làm

1. `cd starter && docker compose up -d --build` — một `app` (BGE-M3 trong image, `EMBED_BACKEND=bge-m3`) + mongo + qdrant. Volume `chatbot-data` + yaml. Image local.
2. Nạp lại 5 Excel sau khi khóa BGE (không trộn vector hash).
3. Bộ câu vàng ≥ 20: `starter/chatbot-api/tests/gold_chat.yaml`. Chạy và ghi % đạt vào P6.md.
4. Đo p95 latency (sau warmup) trên localhost; ghi bảng.
5. README starter: copy → `.env` / yaml / Excel → `compose up --build` (không bước sửa code).
6. `pytest` starter pass.

### Không làm ở P6

Copy sang 8 thư mục phòng. Đổi schema Excel. Đổi model embed khác BGE-M3 (trừ khi có quyết định mới + chạy lại 6.1).

### Cửa ra

- [ ] Compose `starter/` healthy: app + mongo + qdrant.
- [ ] Login Google → nạp 5 file → chat.
- [ ] Production embed = BGE-M3; pytest pass.
- [ ] Gold ≥ 20 câu, đạt ≥ 80%; FAQ nguyên văn; thiếu nguồn không đoán.
- [ ] p95: FAQ ≤ 2s; không-RAG ≤ 3s; RAG+LLM ≤ 15s; embed một câu ≤ 2s.
- [ ] README clone-ready (không “sửa code rồi mới chạy”).

---

## P7 — Clone starter — phòng deploy ngay

**Báo cáo:** `bao-cao-giai-doan/P7.md`

Chỉ khi P6 `ACCEPTED`. Copy `starter/` đè/cập nhật **8 thư mục đơn vị** (kể cả ĐBCL nếu skeleton P0 đã cũ). Mỗi phòng **không** cần sửa Python/JS để lên được.

Mỗi phòng chỉ điền:

- `.env`: `DEPARTMENT_ID`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`, `LLM_API_KEY`
- `department.yaml`: `id` / `name` / `domain` / `admins` / `handoff_form_url`
- 5 Excel 3.0 của phòng

rồi `docker compose up -d --build` trên máy/VM phòng đó.

Không bắt phòng pull image ĐBCL / starter registry. Lệch hành vi chat so với starter = bug P6, vá trên starter rồi copy lại — không vá riêng từng phòng trừ khi phòng cố ý fork.

### Cửa ra

- [ ] 8 thư mục cùng layout starter đã P6.
- [ ] yaml / `DEPARTMENT_ID` đúng mã phòng.
- [ ] Ít nhất **hai** phòng (ĐBCL + một phòng khác) `compose up --build` chạy login → nạp → chat **không** sửa code.
- [ ] Clone một phòng mới: chỉ copy + điền file, không phát sinh bước code.

---

## Sau P7 (không nằm plan này)

Khóa đuôi mail lúc hỏi; SSO; ticket; sảnh 8 link; lọc đối tượng người hỏi.

---

## Xóa khi lập file này (PoC cũ, không phải luồng code mới)

| Đã xóa | Lý do |
|---|---|
| `reports/` | Báo cáo / gold / JSON nghiệm thu phase 0–8 PoC |
| `PHASE_PLAN.md`, `PLAN.md` | Plan PoC Postgres/MinIO/API key |
| `docs/CHECKPOINT.md` | Nhật ký PoC |
| `docs/plan-multi-tenant-routing.md` | Plan routing cũ |
| `docs/decisions/phase-*.md` | Quyết định theo phase PoC |

Giữ: `evaluation/*.py` (script), `app/` / `frontend/` (code hiện tại — gỡ dần từ P0), `template/`, `PLAN_UPDATE.md`, `cautruc8duan.md`.
