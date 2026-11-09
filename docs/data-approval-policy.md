# Chính sách phê duyệt dữ liệu PoC

## 1. Mục tiêu

Workbook PoC hiện không có trạng thái phê duyệt đầy đủ ở từng dòng. Chính sách này dùng release manifest làm nguồn xác định dữ liệu có được phép load, index và sử dụng trong từng môi trường hay không.

## 2. Phạm vi release

Một release là tập hợp đồng bộ của ba file:

1. Thông tin mô-đun.
2. FAQ.
3. Tài liệu nghiệp vụ.

Không approve từng file riêng lẻ vì routing, FAQ và tài liệu phải nhất quán với nhau.

## 3. Release manifest

Mỗi thư mục dữ liệu phòng ban/mô-đun phải có `release-manifest.yaml` chứa:

- `release_id`.
- Department và module.
- Trạng thái release.
- Danh sách file.
- SHA-256 từng file.
- Schema fingerprint từng file.
- Hạn chế đã biết.
- Thông tin business approval.

Nếu checksum không khớp manifest, release không còn hợp lệ và phải tạo manifest/release mới.

## 4. Trạng thái

### `candidate`

- Đã nhận file.
- Được kiểm kê nhưng chưa được index.
- Có thể chạy validation/dry-run.

### `approved_for_dev`

- Được dùng trong môi trường development/test.
- Được load PostgreSQL development.
- Được index Qdrant development.
- Không đồng nghĩa chuyên viên đã duyệt nội dung để UAT.

### `approved_for_uat`

- Chuyên viên phụ trách xác nhận nội dung.
- Contact và URL cần công bố đã được kiểm tra.
- Được dùng cho UAT.

### `retired`

- Không dùng để trả lời.
- Giữ metadata, checksum và lịch sử audit.

## 5. Trạng thái release hiện tại

Release hiện tại được phân loại `approved_for_dev` vì:

- Người thực hiện dự án đã cung cấp đủ ba file làm dữ liệu PoC.
- Dữ liệu được phép dùng để phát triển parser, pipeline và test.
- Chưa có bằng chứng phê duyệt nghiệp vụ chính thức cho UAT.

Business approval vẫn là `pending`.

## 6. Quy tắc kế thừa

Do workbook chưa có status từng dòng:

- Tất cả record hợp lệ kế thừa release status.
- Record validation `ERROR` không được publish dù release đã approved.
- Record `WARNING` được publish trong development nếu policy cụ thể cho phép.
- Một record không thể có trạng thái cao hơn release.

Khi template bổ sung status từng dòng, trạng thái hiệu lực là mức hạn chế hơn giữa row status và release status.

## 7. Quy tắc FAQ thiếu căn cứ

59/71 FAQ hiện chưa có văn bản căn cứ.

- Không coi đây là lỗi schema.
- Gắn validation `WARNING`.
- Được dùng trong development khi release `approved_for_dev`.
- Citation trỏ tới mã FAQ và vị trí nguồn.
- Không tự sinh văn bản căn cứ.
- Trước UAT, chuyên viên phải xác nhận các FAQ này là nội dung trả lời được phê duyệt hoặc bổ sung căn cứ.

## 8. Quy tắc contact

Contact trong dữ liệu hiện được coi là `unverified`.

- Development có thể hiển thị với nhãn dữ liệu thử nghiệm.
- Trước UAT phải xác nhận email, hotline và URL.
- Nếu FAQ thiếu contact, chỉ kế thừa module/department default đã xác nhận.
- Không tự suy ra contact từ Internet hoặc từ phòng ban khác.

## 9. Quy tắc lệ phí chưa xác định

TL02, TL03 và TL04 chưa có mức phí được xác nhận.

- Không chặn ingest development.
- Gắn `fee_type=unknown`.
- Không cho LLM nêu số tiền.
- Câu hỏi về mức phí trả `insufficient_evidence` hoặc `human_handoff`.
- Trước UAT, chuyên viên có thể xác nhận “không thu phí”, mức cố định, tùy trường hợp hoặc tiếp tục để unknown.

## 10. Quy tắc hiệu lực

Workbook hiện không có ngày hiệu lực ở cấp release/record.

- Không suy ra hiệu lực từ ngày tạo hoặc ngày cập nhật file.
- Trong development, release status quyết định quyền sử dụng.
- Trước UAT, chuyên viên phải xác nhận dữ liệu vẫn còn hiệu lực.
- Khi có ngày hiệu lực, retrieval phải lọc:

```text
effective_from is null OR effective_from <= current_date
AND
effective_to is null OR effective_to >= current_date
```

## 11. Điều kiện chuyển sang UAT

Release chỉ được đổi sang `approved_for_uat` khi:

- [ ] Validation không có `ERROR`.
- [ ] Chuyên viên xác nhận tên phòng ban và mô-đun.
- [ ] Chuyên viên xác nhận 71 FAQ.
- [ ] Chuyên viên xác nhận TL01–TL04.
- [ ] Email, hotline và URL công bố đã được kiểm tra.
- [ ] Các nội dung thiếu căn cứ đã được chấp nhận hoặc bổ sung.
- [ ] Lệ phí TL02–TL04 đã có policy rõ ràng.
- [ ] Có tên/ngày/người xác nhận trong manifest hoặc biên bản UAT.

## 12. Thay đổi dữ liệu

Khi bất kỳ file XLSX nào thay đổi:

1. Tính checksum mới.
2. Tạo `release_id` mới.
3. Chạy validation lại.
4. Không tái sử dụng approval cũ tự động.
5. Chuyên viên review phần diff ảnh hưởng.
6. Chỉ index các record thay đổi sau khi release đạt trạng thái phù hợp.

## 13. Audit tối thiểu

Mỗi lần sync phải lưu:

- Release ID.
- File checksum.
- Schema fingerprint.
- Người/kênh kích hoạt sync.
- Thời điểm.
- Số record insert/update/deactivate.
- Validation report.
- Kết quả Silver và Gold.
