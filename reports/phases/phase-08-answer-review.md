# Phase 8 — Đối chiếu mẫu câu trả lời với nguồn

Ngày: 2026-11-11. Người rà soát: Codex. Phạm vi: 10 câu thời hạn được chọn đầu tiên trong bộ Phase 8; 6 câu thiếu hệ đào tạo được trả lời sau lượt làm rõ ĐHCQ. Mẫu có câu trùng chủ đề và không đại diện cho toàn bộ hệ thống. Dữ liệu và citation từng câu nằm trong `phase-08-answer-sample.json`. Sáu câu do Groq sinh được đối chiếu thủ công với các chunk Gold nêu dưới; bốn câu dự phòng được đối chiếu nguyên văn bằng `phase-08-extractive-audit.json`. Đánh giá này không phải phê duyệt nghiệp vụ.

| ID | Kết quả đối chiếu | Căn cứ |
|---|---|---|
| para-phuc-khao-dhcq | Đúng; có nguồn TL02 | `gold:74960109f2605e80fc514869`: ĐHCQ 02 ngày làm việc từ ngày công bố điểm. |
| para-phuc-khao-sdh | Đúng; có nguồn TL02 | Cùng chunk TL02: ĐHCQ 02, SĐH 07 ngày đăng ký; thời hạn kết quả lần lượt 06 và 10 ngày. |
| para-diem-i-nop | Đúng; có nguồn TL03 | `gold:b7241930225d28372f47994b`: 03 ngày làm việc và kênh nộp theo hệ đào tạo. |
| para-diem-i-hieu-luc | Đúng; có nguồn TL03, TL04 | Các chunk `gold:b7241930225d28372f47994b`, `gold:aa7215e268902b55e55e66da`: hiệu lực 01 năm, quá hạn chuyển 0; điều kiện đăng ký khi điểm còn hiệu lực. |
| para-tra-diem-i | Đúng; có nguồn TL04 | `gold:aa7215e268902b55e55e66da`: trước ngày thi đầu tiên của đợt thi 07 ngày. |
| doc-tl02-thoi-han-dhcq | Đúng; trích nguồn | Trích đoạn FAQ và TL02 khớp trực tiếp Gold; có thời hạn ĐHCQ 02 ngày. |
| doc-tl02-thoi-han-sdh | Đúng; trích nguồn | Trích đoạn FAQ và TL02 khớp trực tiếp Gold; có thời hạn SĐH 07 ngày. |
| doc-tl03-ba-ngay | Đúng; có nguồn II.1.036 | Nội dung FAQ II.1.036 trong Gold xác nhận 03 ngày làm việc sau ngày thi. |
| doc-tl03-mot-nam | Đúng; trích nguồn | Trích đoạn TL03 và FAQ II.1.037 khớp Gold, 01 năm và chuyển 0 khi quá hạn. |
| doc-tl04-bay-ngay | Đúng; trích nguồn | Trích đoạn TL04 khớp Gold, trước ngày thi đầu tiên của đợt thi 07 ngày. |

Kết quả mẫu: 10/10 trả lời chứa sự kiện kỳ vọng, nội dung đối chiếu nguồn và citation phù hợp. Trong đó 4/10 là câu trả lời trích nguyên văn khi provider lỗi; vì vậy không thể coi kết quả này là 10 lần đánh giá khả năng sinh của Groq. Chưa suy rộng các tỷ lệ sang toàn bộ tập test; cần đánh giá tập đại diện lớn hơn để chốt KPI chất lượng.
