# Phase 8 — Báo cáo kiểm thử và đánh giá

**Trạng thái: IN_PROGRESS.** Người dùng đã chấp nhận giới hạn quota Groq miễn phí cho PoC ngày 2026-11-11. Đánh giá chất lượng vẫn mới dựa trên mẫu nhỏ nên chưa chốt các KPI chất lượng. Không coi HTTP 200 hoặc trích đoạn dự phòng là generation thành công.

## Kết quả có bằng chứng

| Hạng mục | Kết quả | Giới hạn |
|---|---|---|
| Tập đánh giá | 120 câu: 71 FAQ từ Silver và 49 câu biên soạn | Chỉ áp dụng release development hiện tại. |
| Retrieval hybrid | 100 câu retrieval: Recall@5 100%, MRR 0,957; tập test 42 câu: Recall@5 100%, MRR 0,933. Tenant leak 0 trong 2 truy vấn. | `phase-08-retrieval.json`; threshold 0,4167. |
| FAQ normalized match | 71/71 lookup đúng | `phase-08-faq-match.json` đo trực tiếp SilverFaqStore, không đo toàn bộ graph. |
| Correctness / groundedness / citation | Đối chiếu 10/10 câu mẫu với Gold; 4 câu dùng trích đoạn dự phòng khớp Gold, 6 câu là output Groq. | `phase-08-answer-review.md` và `phase-08-extractive-audit.json`; mẫu nhỏ, tập trung vào 3 chủ đề và có câu gần trùng; không ngoại suy thành KPI toàn bộ test. |
| Mẫu truy xuất mở rộng | 29 câu sau các bản sửa: 28 answered, 1 insufficient; 20 provider fallback, 6 output Groq, 2 câu theo quy tắc. Cả 13 câu có nhãn chuỗi đều chứa cụm kỳ vọng. | `phase-08-answer-expanded.json`; 20/20 fallback khớp đoạn và nhãn trong Gold (`phase-08-extractive-expanded.json`), nhưng điều đó không chứng minh hoàn chỉnh hay phù hợp với câu hỏi. Hai câu routing đã sửa được xác minh riêng. Mẫu trước sửa được lưu riêng. |
| Chính sách / abstention | 17/17 trường hợp đúng: 3/3 insufficient, 4/4 handoff, 5/5 ngoài phạm vi, 5/5 adversarial. | `phase-08-policy.json`; đây là tập nhỏ. |
| 10 VU trên image mới sau warm-up | FAQ p95 0,829 giây; RAG p95 4,720 giây; 0/20 HTTP/application error. | 10 request mỗi loại; p95 là giá trị lớn nhất. 9/10 RAG là provider fallback, nên p95 này không đại diện cho sinh thành công. Cold RAG warm-up 19,082 giây. Image `sha256:deb8c8f7a15c01369e8b03b99fb585029cdf2a8857077f0a9184a1f836a5aab0`. `phase-08-load.json`. |
| Kiểm tra provider dưới tải | 7/10 yêu cầu RAG riêng bị 429, 3/10 không ghi nhận lỗi provider. | `phase-08-provider-load.json`; cho thấy giới hạn thực tế của provider/tài khoản trong lần chạy, không xác định được quota cấu hình hay bảo đảm các lần chạy khác. |
| PostgreSQL | Dump và restore vào database tạm; 13 bảng khớp hash nội dung, bao gồm 71 FAQ và 4 tài liệu. | `phase-08-postgres-restore.json`; so sánh trên DB đang chạy. |
| Qdrant và MinIO | Snapshot Qdrant khôi phục 130 point với payload/vector khớp; restore tạm 5 object MinIO, SHA-256 nội dung khớp. | `phase-08-object-restore.json`; MinIO chưa đối chiếu metadata/versioning; cả hai dùng cùng dịch vụ nguồn. |
| Test và log | 85 unit/health test; browser smoke test đạt; log container benchmark không có key cấu hình hoặc email. | `phase-08-logs.json`; không chứng minh không có mọi loại dữ liệu nhạy cảm hay secret khác. LangGraph và Qdrant local còn cảnh báo. |

## Defect và quyết định

| ID | Mức | Phát hiện | Trạng thái |
|---|---|---|---|
| P8-D01 | P1 | Ngày hiệu lực sai định dạng được coi là không giới hạn. | Đã sửa để loại tài liệu và có regression test. |
| P8-D02 | P1 | Câu hỏi “bao nhiêu tiền” không được nhận diện là lệ phí chưa xác định. | Đã bổ sung biến thể và test, policy 17/17 sau sửa. |
| P8-D03 | P1 | Docker image thiếu FlagEmbedding cho BGE-M3. | Đã thêm dependency CPU; image mới chạy retrieval thật trong container thử. |
| P8-D04 | P1 | Fallback gắn citation cho cả đoạn không hiển thị; câu không trích dẫn được tự gắn nguồn. | Đã chuyển sang trích đoạn và chỉ gắn citation cho các đoạn thực sự hiển thị; có regression test và audit Qdrant. |
| P8-D05 | P1 | Concurrent request khi model chưa tải có thể khởi tạo nhiều model. | Đã thêm lock khởi tạo và regression test 8 thread. |
| P8-D06 | P2 — ngoại lệ PoC | Provider fallback 9/10 ở benchmark image cuối 10 VU (lượt trước 8/10); probe riêng cho thấy 7/10 lỗi 429. | Người dùng chấp nhận hạn chế quota gói miễn phí ngày 2026-11-11. Fallback an toàn và API báo `provider_fallback`; không coi là generation thành công. Cần xem lại capacity trước vận hành rộng hơn. |
| P8-D07 | P2 | Đánh giá thủ công 10 câu hẹp và mẫu mở rộng 29 câu có 20 câu trích xuất; không đại diện cho KPI toàn hệ thống. | Mở. Đã chuẩn bị `phase-08-review-queue.json` gồm 29 câu; cần bổ sung đáp án/căn cứ và review độc lập. |
| P8-D08 | P2 | Cold RAG 19,082 giây; cache model trong thử nghiệm được mount từ host ở chế độ chỉ đọc. | Mở. Cần đánh giá chiến lược cache và warm-up cho môi trường đích. |
| P8-D09 | P2 | Restore MinIO chưa kiểm tra metadata/versioning; Qdrant/MinIO thử trên cùng dịch vụ, không mô phỏng mất host. | Mở. Cần diễn tập trên môi trường độc lập theo mục tiêu khôi phục. |
| P8-D10 | P1 | Groq áp dụng kênh Portal chung cho VB2/VLVH khi trả điểm I dù TL04 quy định qua Phòng Đào tạo; fallback phúc khảo không có nguồn riêng hệ này. | Đã thêm xử lý có căn cứ TL03/TL04 và abstain khi thiếu nguồn VB2 cho phúc khảo. Unit test và ba trường hợp Gold thật đạt: `phase-08-vb2-regression.json`. |
| P8-D11 | P2 | Câu hỏi chung về vắng thi bị chuyển hỗ trợ cá nhân thay vì trả lời quy định chung. | Đã sửa keyword routing; test cá nhân vẫn chuyển hỗ trợ, tình huống Gold thật có citation I.3.023 (`phase-08-absence-regression.json`). |
| P8-D12 | P2 | Hai câu hỏi chung về tra cứu điểm và nộp tiểu luận bị handoff nhầm trong mẫu 29 câu. | Đã bổ sung routing cho câu hỏi chung về kênh; regression bằng Gold thật đạt (`phase-08-channel-regression.json`). Câu có dấu hiệu cá nhân không đi qua quy tắc chung này. |

Các P1 phát hiện trong phạm vi test đã được sửa; giới hạn quota miễn phí được người dùng chấp nhận riêng cho PoC và không được coi là đã khắc phục. Chưa đủ cơ sở chốt KPI answer correctness, groundedness và citation validity toàn tập: cần đánh giá mẫu đại diện hơn hoặc chấp nhận riêng ngoại lệ về phạm vi đánh giá trước Phase 9. Dữ liệu hiện `approved_for_dev`, chưa phải phê duyệt UAT.
