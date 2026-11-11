# Kế hoạch: routing theo Template 1 và kiến trúc đa tenant

## Mục tiêu và hiện trạng

- Một **phòng ban là một tenant**; tenant có một hoặc nhiều mô-đun. Phòng Bảo đảm chất lượng / Khảo khí là cấu hình và dữ liệu thí điểm.
- Template 1 là nguồn nghiệp vụ cho ba nhóm `answer_allowed`, `human_required`, `out_of_scope`. Runtime phải dùng đúng release đang được phép của tenant/mô-đun, không dùng một bảng keyword hoặc prompt khảo thí chung cho mọi mô-đun.
- Thực tế hiện tại: Template 1 được đọc và lưu `routing_rules` trong Silver, nhưng graph dùng `keyword_scope()` rồi prompt LLM cố định, không truy vấn bảng này. Nếu LLM lỗi hoặc không trả enum hợp lệ, graph mặc định `answer_allowed`. Rule-level `bot_behavior` và contact không được graph áp dụng. `human_required` có thể trả FAQ khớp chính xác rồi handoff; `out_of_scope` dùng thông điệp cố định.
- Tenant hiện lấy từ `APP_DEPARTMENT_ID` và `APP_MODULE_CODE`; API key là một khóa chung. Cơ sở dữ liệu và truy xuất Gold đã có trường/lọc department + module, nhưng việc nạp, serializer, prompt, câu trả lời và logic nghiệp vụ còn gắn với BDCL/Khảo khí. Không thể coi việc thêm một block YAML là đủ để onboarding phòng mới an toàn.

## Quyết định thiết kế đề xuất

1. Một API phục vụ nhiều tenant. API key/service identity cấp cho một tenant, có danh sách mô-đun được phép; xác thực tạo `TenantContext` từ thông tin được cấp ở server. Client có thể chọn **module_id trong tenant được phép**, nhưng server phải kiểm tra quyền và trạng thái; không coi tenant/module do client gửi là bằng chứng cấp quyền. Quản trị tenant/config dùng quyền admin riêng. Với browser công khai không phát API key quản trị hoặc service key dùng chung cho người học; cần backend/BFF hoặc cơ chế xác thực phù hợp.
2. Dùng cùng ba template XLSX chuẩn hiện có, có phiên bản schema và release manifest riêng cho mỗi module. Tên sheet/ô và cấu trúc template là data contract có version; không tuyên bố chấp nhận workbook tùy ý. Module mới theo cùng schema không cần sửa mã; schema/nguồn mới cần adapter/version mới và kiểm thử.
3. Template 1 được lưu thành policy có `rule_id` ổn định, `scope_type`, `topic`, mô tả, hành vi có cấu trúc, độ ưu tiên, contact và nguồn. Những cột còn là văn bản tự do được giữ để review và hỗ trợ matching; không thực thi trực tiếp văn bản như lệnh hệ thống. Row không có `bot_behavior` không được tự suy diễn thừa kế khi chưa có quy tắc được xác nhận.
4. Tách policy nền tảng (bảo vệ dữ liệu cá nhân, prompt injection và ranh giới tenant) khỏi policy nghiệp vụ từng module. Thứ tự quyết định: policy nền tảng → rule đang hiệu lực của module → match/LLM đề xuất rule từ danh sách ứng viên có sẵn → server xác minh rule và áp dụng action. LLM không tự tạo rule, địa chỉ liên hệ hoặc quyền.
5. Không khớp, độ tin cậy thấp, rule xung đột, không tải được policy hoặc LLM lỗi: trả `clarification_required`, `human_handoff` hoặc `insufficient_evidence` theo policy được duyệt; không mặc định `answer_allowed`. Chỉ lấy FAQ/RAG sau khi có quyết định cho phép. `human_required` có thể hiển thị FAQ chung đã duyệt nếu policy cho phép; không kết luận hồ sơ cá nhân.
6. Contact chọn từ rule khớp, sau đó module và tenant theo chính sách kế thừa/độ tin cậy đã xác nhận; ngoài phạm vi chỉ hiển thị đích có trong dữ liệu đã duyệt. Không suy đoán tên hoặc thông tin đơn vị khác. Có audit gồm rule_id, version, nguồn, decision, lý do, độ tin cậy và latency; không log API key/PII.
7. Namespace hội thoại/checkpoint theo tenant + module + identity + conversation_id; xác minh quyền sở hữu, chống truy cập chéo hoặc gán lại conversation. Có lựa chọn lưu bền phù hợp khi chạy nhiều worker. Tất cả truy vấn SQL, Qdrant, cache, sync, file/MinIO và log/audit phải giữ ranh giới tenant + module; không dựa vào duy nhất bộ lọc Qdrant.

## Các giai đoạn thực hiện

### 1. Khóa contract và bộ dữ liệu kiểm chứng

- Kiểm kê đủ 17 dòng Template 1 (8 trả lời, 5 hỗ trợ, 4 ngoài phạm vi), các ô hành vi/contact trống, rule giao nhau và các tình huống chưa xác định; xác nhận cách xử lý với chủ sở hữu nghiệp vụ.
- Định nghĩa ID ổn định và migration từ content-based `source_key`; format/version/template, trạng thái duyệt và hiệu lực, rule priority/conflict, contact xác minh, JSON schema và release lifecycle. Giữ backward compatibility cho dữ liệu thí điểm.
- Thiết kế bộ test gán nhãn từ từng dòng Template 1: câu trực tiếp, diễn đạt khác, tình huống cá nhân, đa ý, nhạy cảm, từ khóa trùng giữa các nhóm; bổ sung fixture tenant/module thứ hai có chủ đề và mã tài liệu trùng.
- Quyết định có cần chỉnh XLSX để thêm ID/priority hay mapping bổ sung trong config; không tự gán trạng thái phê duyệt cho dữ liệu thiếu trạng thái.

**Đầu ra:** data contract, migration plan, bộ test và quy tắc precedence/unknown được duyệt.

### 2. Chuẩn hóa ingestion và tenant context

- Bỏ các canonical name cố định khỏi upsert department, validation module, STAIR header, default contact, CLI source path và serializer; lấy tên/audience/context từ config/manifest/Silver. Kiểm tra tên config/manifest nhất quán và module enabled.
- Sửa CLI/sync sử dụng `source_path` được cấu hình khi không truyền tường minh; phân biệt đường dẫn trống với `Path('.')`. Cô lập output và release theo tenant/module/release; khóa đồng bộ theo phạm vi và bảo đảm idempotent.
- Triển khai config registry được validate: tenant, module, template_version, nguồn dữ liệu, release, contact, model/retrieval, policy profile. Không để secret trong YAML; dùng secret store/env tham chiếu.
- API quản trị tối thiểu có xác thực/ủy quyền: xem cấu hình, tạo hoặc cập nhật tenant/module, upload/import dữ liệu, validate/dry-run, kích hoạt release và xem trạng thái job/báo cáo. Ghi audit; activation idempotent và rollback an toàn. Phân biệt thao tác quản trị với chat.

**Đầu ra:** onboarding tenant thứ hai bằng API/config + bộ ba workbook và manifest hợp lệ, không sửa code nghiệp vụ; lỗi validation dễ hiểu và không ghi sang tenant khác.

### 3. Routing từ dữ liệu Template 1

- Thêm `RoutingRuleRepository` đọc Silver theo tenant/module, `is_active`, release/environment, hiệu lực; xử lý cache theo release/version và invalidation sau kích hoạt, không phục vụ policy cũ mãi.
- Xây matcher theo các rule thực tế: exact/alias được cấu hình và semantic/classifier để xếp ứng viên trong phạm vi tenant/module. Chỉ sử dụng các nhãn và ID do server cấp; hiệu chỉnh ngưỡng bằng dữ liệu gán nhãn, không xem điểm semantic đơn thuần là xác suất đã kiểm định.
- Thiết kế bộ giải quyết rule xung đột/đa ý và thiếu thông tin; policy nền tảng không được rule mô-đun ghi đè. Sử dụng `bot_behavior` đã chuẩn hóa để chọn hành động và contact của rule.
- Thay `keyword_scope()` và `ROUTING_SYSTEM` cố định bằng routing context; bỏ fail-open. Chuẩn hóa phản hồi `routing_decision`, `rule_id`, `rule_version`, `reason`, `handoff`/contact, giới hạn nội dung debug theo quyền.
- Test khi sửa một dòng Template 1 và kích hoạt release: hành vi runtime thay đổi tương ứng, không cần sửa code; rule bị thu hồi không tiếp tục dùng. Test timeout classifier, trùng/xung đột, không khớp và prompt injection.

**Đầu ra:** routing của từng mô-đun có thể truy vết về rule đã duyệt; mọi nhánh ba loại phạm vi hoạt động đúng theo policy.

### 4. Tổng quát hóa graph, knowledge và API chat

- Di chuyển các prompt/câu chào/handoff/OOS, topic, hệ đào tạo, deadline, lệ phí và logic riêng TL02–TL04/điểm I/VB2 ra policy/cấu hình mô-đun hoặc extension có version. Giữ các kiểm tra nghiệp vụ đặc thù bằng cấu trúc dữ liệu có thể kiểm chứng; không đơn giản xóa các bảo vệ hiện hữu.
- Cơ chế metadata/clarification theo schema của module; dữ liệu không xác định lệ phí vẫn từ chối nêu mức tiền; tính hiệu lực/ngoại lệ theo evidence đã duyệt. Mã tài liệu/citation phải được so khớp trong đúng tenant/module/release, không giả định `TLxx` là định dạng phổ quát.
- Chat API nhận `module_id` đã ủy quyền, không nhận tenant tùy ý. Cấp quyền theo tenant/module, ràng buộc thread/conversation với context và chủ sở hữu, bảo vệ admin endpoints, giới hạn request và log.
- Tên tenant/module, contact và URLs hiển thị lấy từ context; kiểm tra links, escape nội dung, không để prompt/nguồn của tenant khác xuất hiện. Cập nhật web chat để chọn mô-đun trong danh sách được cấp quyền.

**Đầu ra:** cùng một runtime xử lý ít nhất hai tenant và nhiều module với policy, FAQ, STAIR, câu chào và handoff độc lập.

### 5. Migration, kiểm thử và nghiệm thu

- Migration DB có phiên bản, backfill rule IDs/context/ownership, kiểm tra tenant consistency, chỉ migrate dữ liệu được phép, dry-run và có rollback. Triển khai từng bước sau khi so sánh hành vi cũ/mới trên PoC, không ghi đè dữ liệu nguồn XLSX.
- Contract/integration test qua API + PostgreSQL + Qdrant + MinIO cho 2 tenant, ít nhất 2 module trong một tenant; tenant khác có rule/FAQ/document cùng mã nhưng nội dung và contact khác. Test giả mạo tenant/module, reuse conversation_id, cross-tenant cache, update/deactivate/release rollback và vector leakage.
- Test toàn bộ rule Template 1, ba nhóm phạm vi, paraphrase, conflict, không khớp, thiếu policy, thiếu contact, LLM timeout/429 và payload adversarial. Test PII/handoff và logging. Chạy evaluation/test suite theo từng tenant và release; đo sai phân loại `human_required`/`out_of_scope` thành `answer_allowed` riêng, ngoài các chỉ số tổng thể.
- Chạy regression tính năng Khảo khí: điểm I, VB2/VLVH, phúc khảo, lệ phí chưa xác định, trích dẫn và FAQ; so sánh benchmark, backup/restore và tài liệu vận hành. Thực hiện UAT và chốt ngưỡng với chủ sở hữu nghiệp vụ; dữ liệu `approved_for_dev` không tự trở thành UAT-approved.

**Exit gate:** hai tenant hoạt động trên cùng code; onboarding tenant mới theo contract không sửa code; không có tenant leak ở các bài test; routing trace được rule/release của Template 1; không fail-open khi thiếu policy; các lỗi P0/P1 được đóng; bộ regression thí điểm và UAT đạt hoặc có ngoại lệ được người có thẩm quyền chấp nhận.

## Các câu hỏi cần chốt trước khi triển khai

1. Mô hình chọn module: client được chọn trong danh sách được cấp quyền, hay mỗi API key cố định một module? Đề xuất: key gắn tenant và được cấp danh sách module; client chọn module trong danh sách đó.
2. Khi không phân loại chắc chắn hoặc có nhiều rule mâu thuẫn: hỏi làm rõ trước hay chuyển người hỗ trợ? Đề xuất: hỏi làm rõ khi có thể, handoff khi rủi ro cá nhân hoặc hết lượt; không tự coi là trong phạm vi.
3. Nguồn cấu hình chính là Git/YAML, API quản trị, hay cả hai? Đề xuất: database là runtime registry, API quản trị có audit; YAML là import/export versioned, tránh hai nguồn cùng sửa không đồng bộ.
4. Cho phép sửa Template 1 để thêm ID/priority/status hay cần giữ nguyên? Nếu giữ nguyên, dùng sidecar config có ID ổn định và báo cáo sự khác biệt; không dùng nội dung thay đổi làm định danh lâu dài.
