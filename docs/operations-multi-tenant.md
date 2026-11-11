# Vận hành tenant, mô-đun và policy Template 1

## Kiến trúc đang triển khai

Một phòng là một tenant, có nhiều mô-đun. Registry tên/phạm vi cấu hình được lưu trong `configs/departments.yaml`; API quản trị đọc/ghi cùng file này với khóa liên tiến trình, ETag và bản cấu hình cũ trong `.registry-history`. Đây là nguồn cấu hình duy nhất của bản triển khai hiện tại. Silver lưu policy/FAQ/tài liệu đã sync. Chưa triển khai database registry riêng hoặc điều phối nhiều host không dùng chung storage; không trộn hai nguồn cấu hình có thể sửa độc lập.

Runtime production đọc rule Template 1 từ Silver theo tenant/mô-đun, trạng thái duyệt, `is_active` và release hiện hành của module. Exact topic/alias cấu hình được ưu tiên; còn lại LLM chỉ được chọn ID trong danh sách rule đã cung cấp. Server lấy `scope_type` từ rule đó, không nhận nhãn do LLM tự gán. Không có rule, ID bịa, conflict exact hoặc lỗi classifier đều không cho phép FAQ/RAG. Rule contact chỉ hiển thị theo điều kiện xác minh/môi trường; nếu thiếu thì kế thừa module/tenant. Output có `rule_id` và `rule_version`.

`legacy_mode=True` là đường tương thích cho bộ test cũ, không được dùng bởi `AgentRuntime.from_settings` hay HTTP runtime. Test production mới chạy policy từ repository; không dùng keyword khảo thí làm quyền mặc định.

Profile `generic` mặc định không chạy các quy tắc metadata đặc thù khảo thí. Profile `assessment` là extension hiện hữu cho Khảo khí, gồm nhận diện hệ đào tạo, thời hạn, lệ phí và ngoại lệ điểm I; policy ngoại lệ được tách vào `app/agent/assessment.py`. Module mới theo cùng template dùng generic và không cần sửa code; một loại tích hợp hoặc một thuật toán nghiệp vụ đặc thù mới vẫn cần extension được kiểm thử.

## Cấu hình credentials

`API_CLIENTS` là JSON array qua environment/.env, không lưu secret trong registry:

```json
[{"id":"finance-service","department_id":"finance","modules":["payments"],"api_key":"replace-with-a-real-long-secret"}]
```

`APP_ADMIN_API_KEY` là secret riêng ít nhất 16 ký tự. Nếu chưa đặt, các endpoint quản trị bị khóa. Nếu đã có `API_CLIENTS`, key chung `APP_API_KEY` không còn được dùng cho chat. Nếu chưa có, key cũ chỉ được quyền tenant/mô-đun cố định từ cấu hình PoC để tương thích. Thay credential environment cần restart; sửa registry không cần restart. Mỗi client ID phải ổn định và duy nhất; không tái cấp một client ID cho một chủ thể khác.

Hội thoại được namespace theo tenant, module, môi trường, client ID và conversation ID. Đây là cô lập theo service identity; nếu nhiều người học dùng chung service key thì cần BFF/end-user identity trước khi cung cấp giao diện công khai. Checkpoint hiện vẫn in-process; chưa hỗ trợ lịch sử bền và chia sẻ giữa worker.

## API quản trị và onboarding

Swagger `/docs` (không phải UAT) liệt kê health, chat và **administration**. Authorize bằng `X-Admin-Key` để gọi ETL. Ba workbook chuẩn nằm trong `template/` (Template 1 phạm vi, Template 2 FAQ, Template 3 tài liệu). Module mới cùng schema không sửa code; `profile=generic` trừ khi cần extension khảo thí.

Luồng nạp phòng mới đến Qdrant:

1. Điền ba file theo `template/`, đổi tên cho đúng phòng/mô-đun nếu cần.
2. `POST /v1/admin/packages/inspect` với ba XLSX base64: API nhận diện role bằng schema fingerprint, sinh `release-manifest.yaml` (checksum + expected_counts).
3. `POST /v1/admin/releases` cùng files, `department_*`, `module_*`, `release_id`, `profile=generic`. `dry_run=true` ghi registry + thư mục `data/{tenant}/{module}/{release}` và validate, chưa ghi MinIO/Postgres/Qdrant. `dry_run=false` chạy đủ Bronze → Silver → Gold (Qdrant).
4. Cấp `API_CLIENTS` cho tenant/module rồi restart khi đổi key. Chat lấy policy/FAQ/vector mới không cần sửa graph.

Có thể tách bước: `PUT /v1/admin/registry` → `POST /v1/admin/sources` (kèm manifest) → `POST /v1/admin/sync`. `GET /v1/admin/tenants` và `GET /v1/admin/reports/{department}/{module}` xem trạng thái.

1. `GET /v1/admin/registry`, header `X-Admin-Key`: lấy registry và ETag.
2. Thêm tenant/module vào JSON trả về, đặt `source_path` thành đường dẫn release mới dưới `data/`, `profile=generic`, tên và contact phù hợp. `PUT /v1/admin/registry` với `X-Admin-Key` và `If-Match` bằng ETag hiện tại. ETag cũ bị 409, nguồn trùng giữa module hoặc đường dẫn ngoài `data/` bị từ chối.
3. `POST /v1/admin/sources`, `X-Admin-Key`, body `{department_id,module_code,files:{filename:base64_bytes}}`. Gói gồm ba XLSX theo template chuẩn và `release-manifest.yaml` có checksum/fingerprint, context và trạng thái được phép. Không ghi đè thư mục nguồn đã tồn tại; cấu hình đường dẫn release mới khi cập nhật. Giới hạn upload mặc định 16 MiB, cấu hình `SOURCE_UPLOAD_MAX_BYTES`.
4. `POST /v1/admin/sync`, body `{department_id,module_code,dry_run:true}`: kiểm tra manifest, schema, checksum, counts và context. Sửa lỗi trước khi sync thật.
5. Gọi lại với `dry_run:false` để ghi Bronze/Silver/Gold. Kiểm tra cả `status`, lỗi và thống kê; HTTP 200 không tự nghĩa là toàn bộ sync thành công. Nếu Gold lỗi sau Silver, runtime sẽ loại vector không khớp release và trả thiếu bằng chứng thay vì dùng dữ liệu cũ. Sync đang chạy đồng bộ, chưa có hàng đợi job hoặc chuyển release nguyên tử nhiều kho.
6. Cấp client key với tenant/modules trong `API_CLIENTS`, restart khi đổi credentials. `GET /v1/modules`, `X-API-Key`: danh sách module được phép. `POST /v1/chat` nhận `{message,module_code,conversation_id?}`. Tenant do server suy ra từ key; không nhận `department_id` trong body. Nếu key có nhiều module, phải chọn module rõ ràng. Web chat có nút tải và chọn module.

Để phục hồi registry: `GET /v1/admin/registry/revisions/{sha256}` bằng admin key, review bản cũ, rồi PUT lại với ETag hiện hành. Đây là rollback cấu hình; chưa phải rollback nguyên tử dữ liệu Silver/Gold. Việc source release được duyệt vẫn tuân theo manifest/môi trường, không được tự coi dữ liệu development là UAT-approved.

## Template 1 và alias

Template A:G cũ tiếp tục đọc được. Có thể thêm header H9 `rule_id` hoặc `MÃ PHẠM VI`, điền ID ổn định cho từng dòng ở cột H. ID tối đa 64 ký tự, phải duy nhất trong module; dùng cùng ID khi sửa mô tả để giữ định danh. Sau thay đổi workbook phải cập nhật checksum manifest. Nếu chưa có ID, vẫn dùng content-based source key; sửa topic sẽ tạo rule ID khác, dòng cũ bị ngưng dùng khi sync. Không tự sửa file dữ liệu nguồn hiện tại.

Registry có `routing_aliases: {rule_id: [câu hỏi chính xác, ...]}` để cấu hình đường đi không gọi LLM. Alias chỉ có hiệu lực nếu ID thực sự nằm trong release được phép. Hai rule cùng match không tự chọn rule cho phép trả lời. Văn bản `bot_behavior` được đưa vào classifier như mô tả nghiệp vụ; chưa có DSL thực thi tùy ý cho yêu cầu thu thập biến/handoff workflow. Ba hành vi runtime vẫn là trả lời có nguồn, FAQ chung + handoff, hoặc ngoài phạm vi + contact.

## Docker và migration

Image có cấu hình mặc định; Compose dùng volume riêng cho registry, nguồn upload, reports và cache embedding. Volume registry đã có sẽ không tự nhận thay đổi file trong image mới: import qua API/ETag. Không mount API key quản trị vào client browser.

Gold mới có `release_id` trong payload và content hash tính cả release. Sau cập nhật mã cần rebuild/incremental Gold cho từng module; vector cũ thiếu release không được runtime production dùng khi rule đã có release. Bộ cũ không được đánh giá là tương thích hoàn toàn chỉ vì test keyword cũ còn pass. STAIR lấy tên phòng/mô-đun và nhãn đối tượng từ config (`nguoi_hoc` → Người học); không hard-code BDCL.

Nếu generate không kèm mã nguồn khớp evidence (TLxx, mã câu hỏi, chunk_id đúng như mục Mã, hoặc mã tài liệu generic), runtime thay bằng trích đoạn STAIR đã duyệt khi còn evidence đọc được; không hiện câu LLM đã bịa citation. Đây là trả lời extractive, không tính generation thành công. Container API chính không tự restart khi build image mới; kiểm tra image trên cổng thử rồi mới quyết định deploy.

## Giới hạn nghiệm thu còn lại

Đã có test quyền tenant/module, classifier lỗi/ID sai, rule contact, thay đổi config/disable, namespace hội thoại, stable rule ID, SQLite policy filtering và PostgreSQL onboarding tenant mới. Chưa coi bản này là hoàn tất mọi nội dung trong kế hoạch: database registry, job API bất đồng bộ, activation/rollback nguyên tử nhiều kho, xác thực người dùng cuối, audit theo từng operator và workflow hành vi tùy ý chưa triển khai. Cần đánh giá routing thật trên 17 rule + paraphrase và tenant thứ hai sau migration, đặc biệt khi Groq miễn phí trả quota/timeout.
