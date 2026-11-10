# Báo cáo Phase 4 — STAIR, embedding và Gold Layer

## 1. Metadata

| Thuộc tính | Giá trị |
|---|---|
| Phase | 4 |
| Trạng thái | `ACCEPTED` |
| Ngày bắt đầu | 2026-11-10 |
| Ngày kết thúc | 2026-11-10 |
| Phạm vi | Phòng Bảo đảm chất lượng / Mô-đun Khảo khí |
| `department_id` | `bao_dam_chat_luong` |
| `module_code` | `khao_khi` |
| Người thực hiện | Lê Gia Văn / dự án UEL Innovation |
| Commit/Tag | Working tree Phase 4 (chưa commit) |

## 2. Mục tiêu

- Serialize Silver thành STAIR Markdown đọc độc lập.
- Embed local `BAAI/bge-m3` (dense + sparse) trên CPU.
- Index Qdrant Gold với hard filter tenant; upsert incremental; rebuild từ PostgreSQL.
- FAQ cùng collection, cộng điểm ưu tiên lúc search. Exact match SQL giữ cho Phase 6.
- Không index routing. Không nhúng email/hotline/secret vào STAIR.

## 3. Checklist hoàn thành

- [x] P4.01–P4.06 — STAIR, metadata, không tách thời hạn/lệ phí, chunk ID.
- [x] P4.07 — Benchmark BGE-M3 CPU (query embed ~0.47s sau khi load).
- [x] P4.08–P4.09 — Khóa BGE-M3, không benchmark e5.
- [x] P4.10–P4.16 — Collection named vectors, payload index, filter, incremental, rebuild.
- [x] P4.17 — STAIR ẩn email/hotline; scanner PII = 0 trên live index.

## 4. Deliverables

| Deliverable | Đường dẫn | Trạng thái |
|---|---|---|
| Quyết định Phase 4 | `docs/decisions/phase-04-decisions.md` | Hoàn thành |
| Gold package | `app/gold/` | Hoàn thành |
| CLI | `rebuild-gold`, `gold-verify`, `--skip-gold` | Hoàn thành |
| Evidence live | `reports/phases/phase-04-evidence.json` | Hoàn thành |
| STAIR dump | `reports/gold/` (gitignored) | Hoàn thành |

## 5. Kết quả kiểm tra

| Kiểm tra | Kỳ vọng | Kết quả | Evidence |
|---|---|---|---|
| Live Qdrant points | FAQ + TL01–TL04 | 130 | `phase-04-evidence.json` |
| Entity mix | FAQ 71 + docs | 71 faq, 15 regulation, 25 condition, 3 procedure, 3 dossier, 13 step | |
| Release | `approved_for_dev` | 130/130 | |
| PII/secret trên STAIR | 0 | 0 | email nguồn đã ẩn |
| Tenant leak `other_department` | 0 hit | 0 | |
| Incremental lần 2 | 0 upsert | unchanged=130, upserted=0 | |
| Smoke 6 câu PoC | khớp từ khóa | 6/6 `expect_matched=true` | |
| Hard filter | mọi hit cùng department | `bao_dam_chat_luong` | |
| Query embed CPU | ghi số | 0.47s / 1 câu sau load | dense 1024 + sparse |

26 condition Silver → 25 chunk Gold: một ngoại lệ gắn vào regulation cùng chủ đề. 4 dossier item → 3 chunk (một chunk hồ sơ / thủ tục TL02–TL04).

### 5.1. Benchmark embedding

| Thuộc tính | Giá trị |
|---|---|
| Model | `BAAI/bge-m3` |
| Device | CPU |
| Dense | 1024, cosine |
| Sparse | lexical weights (FlagEmbedding) |
| Fusion | Qdrant RRF |
| Batch size | 2 (CPU; mặc định thư viện 256 làm treo Windows) |
| Query embed | ~0.47 s (model đã load) |
| RAM | Trọng số ~2GB; chạy host, không đo RSS trong PoC |

### 5.2. Smoke search (2026-11-10)

Mọi câu trả về 5 hit, `department_id` đúng tenant:

| Câu | Top entity | Khớp từ khóa |
|---|---|---|
| Thời hạn phúc khảo ĐHCQ | regulation TL02 | Có |
| Thời hạn phúc khảo SĐH | regulation TL02 | Có |
| Nộp đơn nhận điểm I | procedure TL03 | Có |
| Trả điểm I / thi bổ sung | procedure TL04 | Có |
| Điện thoại trong phòng thi | FAQ II.2.047 | Có |
| Lệ phí phúc khảo | procedure TL02 | Có |

Recall@k chính thức đo ở Phase 5.

## 6. Exit gate

| Điều kiện | Kết quả | Ghi chú |
|---|---|---|
| Chunk độc lập có chủ đề và đối tượng | Pass | Header STAIR phòng ban / Khảo khí / Người học |
| TL02–TL04 giữ thời hạn và ngoại lệ | Pass | Smoke TL02–TL04; lệ phí không nêu số tiền |
| Không index dữ liệu chưa duyệt | Pass | Chỉ `approved_for_dev` |
| Filter `department_id` trên mọi query | Pass | tenant leak = 0 |
| Rebuild từ PG tương đương | Pass | incremental 130 unchanged |
| Ghi model, dimension, thời gian | Pass | mục 5.1 |

## 7. Quyết định kỹ thuật (Phase 4)

| ID | Quyết định | Lý do |
|---|---|---|
| DEC-P4-01 | FAQ + tài liệu một collection, boost FAQ | DR-P4-01…03 |
| DEC-P4-02 | BGE-M3 dense+sparse, batch CPU = 2 | Tránh treo batch 256 |
| DEC-P4-03 | Ẩn email/hotline trong STAIR | Nguồn có `phongbdcl@uel.edu.vn` trên bước thủ tục |
| DEC-P4-04 | `gold-verify` là lệnh nghiệm thu Gold | Đếm, PII, incremental, smoke |

## 8. Blocker và ngoại lệ

| ID | Nội dung | Owner | Hạn xử lý | Ảnh hưởng |
|---|---|---|---|---|
| — | Không có blocker | — | — | — |

Contact YAML vẫn `verified: false`. Exact match SQL và rerank cross-encoder không nằm Phase 4.

## 9. Rủi ro chuyển Phase 5

- Smoke ≠ Recall@5; cần bộ ≥ 80 câu, tách calibration/test.
- Hybrid RRF chưa so với dense-only bằng số liệu retrieval.
- Host CLI phải `QDRANT_URL=http://localhost:6333`.
- FAQ DATA-05 (thiếu căn cứ) đang trong Gold development.

## 10. Kết luận

**Kết quả: `ACCEPTED`**

Phase 4 đã index 130 chunk Khảo khí lên Qdrant, filter tenant, incremental ổn định, STAIR không PII. Phase 5 có thể bắt đầu: retrieval baseline và bộ đánh giá.
