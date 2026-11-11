# Phase 7 — FastAPI, API key và web chat

Kết quả: **ACCEPTED** theo exit gate Phase 7.

- API `POST /v1/chat` dùng API key, cấu hình tenant phía server, request ID, giới hạn request, timeout và CORS theo cấu hình.
- Health checks báo trạng thái dependency. Web chat hiển thị trạng thái, citation và thông tin hỗ trợ; nội dung được gán qua `textContent`.
- `pytest tests/unit tests/smoke/test_health.py -q -p no:cacheprovider --basetemp .phase7-pytest-temp`: 76 passed. Bao gồm kiểm tra key thiếu/sai, log, tenant, CORS, timeout, lỗi dịch vụ và readiness.
- `pytest tests/smoke/test_browser_chat.py -q -p no:cacheprovider` với Chrome cục bộ: 1 passed. Test dùng response giả để kiểm tra thao tác chat, citation và không render HTML.
- Người dùng xác nhận test ứng dụng thành công; chi tiết từng thao tác không được ghi lại. Browser smoke tự động không kiểm tra provider thật.
- Ruff trên các file Phase 7: passed. Cảnh báo LangGraph deprecation và Qdrant local vẫn còn.

Giới hạn: hội thoại dùng MemorySaver trong tiến trình; khởi động lại mất lịch sử và các worker không chia sẻ lịch sử. Timeout HTTP không dừng thread đã bắt đầu. Dữ liệu vẫn cần business duyệt trước UAT; đánh giá chất lượng, kiểm thử tải, isolation mở rộng và backup/restore thuộc Phase 8.
