# CHECKPOINT — đọc file này trước khi tiếp tục

Cập nhật: 2026-11-11. Workspace: D:\ITAC\UEL-Innovation.

## Yêu cầu đang làm

Người dùng yêu cầu chuẩn hóa thật sự theo `docs/plan-multi-tenant-routing.md`: Template 1 phải điều khiển routing; một phòng là một tenant, có nhiều module; vận hành chủ yếu bằng API/config, không phải sửa code mỗi lần onboarding theo cùng template. Người dùng cho phép hỏi khi cần làm rõ, ưu tiên chủ động làm. Tin nhắn mới: khi context gần 5% hãy ghi báo cáo để lần context mới chỉ cần đọc và tiếp tục. Không có tool đo chính xác phần trăm context; đã nói sẽ checkpoint thường xuyên.

KHÔNG coi tin nhắn checkpoint là hủy công việc chuẩn hóa. Tiếp tục từ trạng thái hiện tại, không làm lại từ đầu, không báo hoàn thành mọi mục trong plan khi còn thiếu.

## Quyết định và quyền đã có

- Tenant = department; module nằm trong tenant.
- Chat key gắn với tenant và danh sách module; server suy ra tenant, client chỉ chọn module đã được cấp quyền.
- Quota Groq miễn phí được người dùng chấp nhận như hạn chế PoC. Người dùng cũng chấp nhận phạm vi mẫu đánh giá 29 câu của Phase 8. Phase 8 bị gián đoạn trước khi cập nhật trạng thái cuối; hiện vẫn IN_PROGRESS trong báo cáo, không tự giả định đã chốt.
- Không spawn subagent (developer cấm trừ khi user/skill yêu cầu).
- Không sửa XLSX nguồn; có file lock Excel của user xuất hiện trong data, không chạm vào.
- Các file cũ Phase 7/8 và các thay đổi chưa commit là công việc của phiên này; không reset/revert/xóa bừa.
- Đã đọc skill Sites trong cuộc hội thoại trước cho giao diện; task hiện là backend/config, không cần tạo/publish Sites.

## Phát hiện nền

Template 1 đã parse 17 dòng vào Silver nhưng trước đây runtime chỉ dùng keyword và prompt khảo thí cố định, LLM lỗi mặc định cho phép trả lời. Code có canonical BDCL/Khảo khí ở writer, validation, STAIR, prompt. Cơ sở dữ liệu và Qdrant đã có bộ lọc tenant/module.

## Đã triển khai trong lượt chuẩn hóa này

1. `app/agent/policy.py`: `SilverRuleStore` tải các rule theo tenant/module/is_active/release_status/environment và rule.release_id == Module.release_id; classifier chỉ trả ID hiện hữu. `ScopeRule` gồm scope/topic/behavior/contact/release/version. Policy version đang release_id + content_hash.
2. `app/agent/graph.py`: `from_settings` dùng SilverRuleStore; runtime đọc config module enabled/name/profile, namespace checkpoint bằng SHA256(tenant,module,environment,principal,conversation). Production routing không dùng keyword: exact topic/configured aliases trước rồi classifier theo rule Template 1. Unknown ID, thiếu rule, classifier lỗi -> hỏi rõ/handoff, không retrieval. Rule contact dùng đúng rule và verified/env. Trace rule_id/version trả về ChatResult/API. Generic prompt/chào/OOS theo context; generic profile bỏ qua metadata/clarification khảo thí. `legacy_mode=True` chỉ được đặt ở helper test cũ; production default False.
3. `app/agent/assessment.py`: đã tách xử lý ngoại lệ VB2/điểm I khỏi evidence_gate dùng chung, chỉ chạy profile assessment. Phần detect/metadata khảo thí còn là extension được gọi khi profile assessment; các nghiệp vụ mới ngoài generic vẫn cần extension có test, không tuyên bố đã có DSL policy tùy ý.
4. `app/api/auth.py`: API_CLIENTS credentials typed SecretStr, identity + tenant/modules, constant-time key compare. Key PoC legacy chỉ được dùng khi API_CLIENTS rỗng. `/v1/chat` nhận module_code (tenant không được client truyền), kiểm tra enabled/grant mỗi request, principal namespace. `/v1/modules` liệt kê module được cấp quyền.
5. `app/api/routes/admin.py`: admin key riêng (mặc định khóa nếu chưa đặt), GET/PUT registry với ETag + If-Match + portalocker + atomic file replace + history; GET old revision; POST sources (base64 package filenames bounded, dưới data, immutable directory, tránh traversal/overwrite); POST sync dry-run mặc định true, dùng config path và Settings đúng instance cho Bronze/Silver/Gold.
6. Registry hiện dùng **YAML là nguồn duy nhất**, không phải DB registry đã đề xuất ban đầu. Đã ghi rõ trong `docs/operations-multi-tenant.md`; API/config cùng đọc ghi file đó, lock giữa worker trên cùng filesystem. Chưa có DB registry/multi-host control plane, job queue, activation/rollback nguyên tử nhiều kho, operator-specific audit, end-user auth hay durable shared checkpoints. Cần trung thực về phần chưa hoàn tất.
7. `app/ingestion/manifest.py`: config generic profile mặc định, profile assessment explicit ở configs/departments.yaml; description/routing_aliases; ID slugs, unique tenant/module; source_type Literal xlsx/google-sheets.
8. Generic ingestion: writer dùng config.name thay canonical BDCL; module validation theo manifest; CLI lấy source_path từ config khi không truyền, pipeline không fallback âm thầm khi explicit source không tồn tại; reports namespace tenant/module/release; tên config/manifest phải nhất quán.
9. `app/gold/stair.py` và builder: truyền tên phòng/module thực tế thay canonical. Payload Gold mới có release_id, content_hash tính cả release; graph không dùng hit khác/thiếu release khi selected rule có release. FAQ SQL phải khớp Module release và active/approval. Lưu ý các serializer audience còn default người học, cần xem nếu mở ngoài đối tượng sinh viên.
10. Template 1 optional cột H9 `rule_id` hoặc `MÃ PHẠM VI`: ID ổn định tối đa64, unique kiểm tra; nếu chưa có tiếp tục content-based key. Không sửa XLSX hiện tại; checksum manifest phải cập nhật khi người vận hành sửa source.
11. Dockerfile copy configs và tạo chown thư mục data/reports/HF; Compose thêm named volumes api_config/api_sources/api_reports/embedding_cache. Image/runtime config volume có dữ liệu sẽ không tự nhận file mới trong image; cập nhật qua API. Container chính hiện tại CHƯA được thay thế/restart.
12. Web chat generic title, có tải/chọn module; đổi key/module reset conversation. API keys vẫn service identities; cần BFF nếu public.
13. Docs: `docs/operations-multi-tenant.md` có vận hành, endpoints, .env/API_CLIENTS, migration và giới hạn. `docs/plan-multi-tenant-routing.md` là plan trước đó.

## Kiểm chứng đã có

- SilverRuleStore đọc **17 rule thật** từ PostgreSQL PoC: 8 answer_allowed, 5 human_required, 4 out_of_scope.
- Unit suite lần gần đây: 91 passed (trước khi thêm 2 test cuối), test tenant mới riêng tổng 7 rồi thêm stale release test (chưa chạy toàn bộ lần cuối). Một lần test mới fail chỉ vì thiếu import Path trong test; đã sửa.
- Các test mới `tests/unit/test_tenant_policy.py`: rule đổi hành vi, rule contact đúng tenant, fail-closed, namespace clarification chống chéo tenant, auth module403/tenant422, admin auth401, ETag stale409, source traversal422/overwrite409, config disable có hiệu lực; SQLite SQL rule tenant/module/approval/release; explicit rule ID survives topic edits; generic finance ingestion dry-run.
- PostgreSQL integration 5 test cũ pass trên DB riêng `uel_rag_test_standardization_20261111`; test mới `tests/integration/test_tenant_onboarding.py` pass (1): Finance/payments lưu tên đúng, Gold headers đúng, payload release đúng, policies3 và tenant khác0.
- Fixture integration đã thêm TEST_POSTGRES_DB, chỉ cho tên `uel_rag_test[a-z0-9_]*`; không bao giờ chạy xóa test tables trên DB PoC.
- **Gold migration thật đã hoàn tất**: `rebuild-gold --incremental` cho bao_dam_chat_luong/khao_khi, 130 chunks/upserts, 0 delete, collection uel_knowledge, BAAI/bge-m3. Session 97764 đã exit0. Đây là cập nhật có chủ đích thêm release_id + header generic. Không chạy lại không cần thiết.
- Ruff trên các file vừa sửa đã pass.
- Mypy đã pass 4 file mới/chính: app/agent/policy.py, app/api/auth.py, app/api/routes/admin.py, app/api/routes/chat.py với --follow-imports=silent. Vừa sửa các annotation/return type/typed runtime để pass.

## Tiến trình đang chạy cần tiếp tục kiểm tra

- Không còn docker build / gold rebuild / smoke / pytest chạy. Image mới đã tag `uel-rag-poc-api:standardization`. Container chính không restart.
- DB kiểm thử `uel_rag_test_standardization_20261111` đã drop sau khi 6 integration pass. Không đụng `uel_rag`.

## Việc cần tiếp tục

Các mục test/citation/image thử/báo cáo của lượt hoàn thiện dở dang đã làm. Phần còn lại là kiến trúc plan chưa triển khai (DB registry, job API, rollback nguyên tử, end-user identity, DSL workflow) và quyết định deploy container chính — xem mục trạng thái dừng mới nhất.

## Các chú ý an toàn và tool

- PowerShell pipe Python stdin làm hỏng chữ tiếng Việt (trở thành '?') khi source chứa literal Unicode. Dùng apply_patch cho Unicode hoặc PowerShell Set-Content -Encoding utf8; Python scripts nên ASCII với \u escapes. Get-Content phải -Encoding utf8.
- Tools qua functions.exec; tools.write_stdin session khác functions.wait cell. Chỉ functions.wait khi exec trả cell ID.
- Docker commands nhiều cái đã approved; khi permission/network failure do sandbox phải retry require_escalated đúng quy định. Không in .env, API keys, raw provider errors.
- Need progress commentary ít nhất mỗi ~60 giây, không hỏi trong commentary; câu hỏi cần dùng async tool nếu thiếu quyết định thật.

---
# TRẠNG THÁI DỪNG MỚI NHẤT — 2026-11-11 (lượt hoàn thiện dở dang)

Người dùng yêu cầu hoàn thiện phần dở dang. Đã làm xong các mục kiểm thử/sửa citation/image thử/báo cáo bên dưới. **Không tuyên bố hoàn tất toàn bộ plan** (`docs/plan-multi-tenant-routing.md`). Báo cáo: `reports/phases/standardization.md`.

## Đã chốt trong lượt này

- Citation: generate không còn bắt buộc `gold:...` hex; extract mã tài liệu generic từ evidence; citation sai/thiếu thì fallback extractive khi còn đoạn STAIR đọc được (không hiện câu LLM bịa nguồn). Unit: `test_invalid_citation_falls_back_to_extractive`, `test_invented_gold_citation_falls_back_to_approved_excerpt`.
- STAIR audience lấy từ config (`nguoi_hoc` → Người học); builder truyền audience. Không rebuild Gold 130 (nhãn BDCL không đổi).
- `test_tenant_onboarding.py` gắn `pytest.mark.integration`.
- Unit+health **94 passed**; browser **1 passed** (có tải/chọn module); mypy 5 file chính pass; Ruff pass.
- Integration trên DB `uel_rag_test_standardization_20261111`: 5 test cũ + onboarding Finance/payments.
- Groq smoke 3 câu: OOS và handoff đúng; xin điểm I routing đúng, **answered extractive** (trước là insufficient_evidence). Không tính generation thành công. File `reports/phases/standardization-routing-smoke.json`.
- Docker image mới `uel-rag-poc-api:standardization` (`sha256:ffe6506e54f6…`). Container thử 18080: live/ready 200, modules 401/200, admin 401, module lạ 403. Đã xóa container thử. **Container chính vẫn image `sha256:db31e91062ed…`, không restart.**
- README + `docs/operations-multi-tenant.md` cập nhật đúng phần chưa có.

## Còn lại (không làm trong lượt này)

1. Deploy/restart container chính khi người dùng chỉ định.
2. DB registry, job API, activation/rollback nguyên tử nhiều kho, end-user identity/BFF, durable shared memory, operator audit, DSL `bot_behavior`.
3. Đánh giá 17 rule + paraphrase + UAT; Phase 8 KPI vẫn IN_PROGRESS.
4. Groq generate vẫn thường không cite đúng nên câu RAG có thể ra extractive; cải generation/citation nếu cần tỷ lệ tóm tắt LLM cao hơn.

Không sửa XLSX nguồn. Không spawn subagent.
