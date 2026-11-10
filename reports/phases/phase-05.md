# Báo cáo Phase 5 — Retrieval baseline và bộ đánh giá

## 1. Metadata

| Thuộc tính | Giá trị |
|---|---|
| Phase | 5 |
| Trạng thái | `ACCEPTED` |
| Ngày bắt đầu | 2026-11-10 |
| Ngày kết thúc | 2026-11-10 |
| Phạm vi | Phòng Bảo đảm chất lượng / Mô-đun Khảo khí |
| `department_id` | `bao_dam_chat_luong` |
| `module_code` | `khao_khi` |
| Người thực hiện | Lê Gia Văn / dự án UEL Innovation |
| Commit/Tag | Working tree Phase 5 (chưa commit) |

## 2. Mục tiêu

- Đóng bộ đánh giá retrieval ≥ 80 câu (FAQ verbatim + paraphrase + TL01–TL04 + policy + adversarial + tenant leak).
- Tách calibration / test; đóng băng test set bằng `dataset_sha256`.
- Đo Recall@1, Recall@5, MRR trên hybrid (BGE-M3 dense+sparse RRF) và so với dense-only.
- Hiệu chỉnh `top_k` và score threshold trên calibration, không tối ưu trên test.
- Xác nhận không tenant leak và câu hỏi thời hạn theo hệ đào tạo lấy đúng tài liệu.

## 3. Checklist hoàn thành

- [x] P5.01 — 71 FAQ verbatim sinh từ Silver (`faq-verbatim-{question_code}`).
- [x] P5.02 — 15 paraphrase, `exact_match_eligible: false`.
- [x] P5.03 — Retrieval TL01–TL04 (`doc-tl01` … `doc-tl04`).
- [x] P5.04 — Câu phân biệt ĐHCQ / SĐH / VB2–VLVH.
- [x] P5.05–P5.07 — Ngoài phạm vi, handoff, thiếu dữ liệu (lệ phí).
- [x] P5.08 — 5 adversarial / prompt injection.
- [x] P5.09 — Calibration vs test: FAQ `sha256(question_code)[0] % 3 == 0` → test; authored gán sẵn.
- [x] P5.10 — Recall@1 / @5 / MRR.
- [x] P5.11 — Hybrid vs dense-only.
- [x] P5.12 — `top_k=5`; threshold khuyến nghị 0.4167 từ calibration R@1.
- [x] P5.13 — Test set đóng băng `dataset_sha256=1423dd9a…35ff1f52`.
- [x] P5.14 — Baseline JSON/Markdown và báo cáo phase.

## 4. Deliverables

| Deliverable | Đường dẫn | Trạng thái |
|---|---|---|
| Authored cases | `evaluation/cases.yaml` | Hoàn thành |
| Eval package | `app/evaluation/` | Hoàn thành |
| CLI | `python -m app.cli eval-retrieval` | Hoàn thành |
| Baseline JSON | `reports/phases/phase-05-baseline.json` | Hoàn thành |
| Baseline Markdown | `reports/phases/phase-05-baseline.md` | Hoàn thành |

## 5. Kết quả kiểm tra

Tổng 115 case: 97 retrieval (71 FAQ + 15 paraphrase + 11 document) + 11 policy + 5 adversarial + 2 tenant leak.

| Kiểm tra | Kỳ vọng | Kết quả | Evidence |
|---|---|---|---|
| Retrieval cases | ≥ 80 | 97 | `phase-05-baseline.json` |
| Hybrid Recall@5 test | ≥ 85% | **100%** (39 câu) | frozen test |
| Hybrid Recall@5 all | — | 100% (97 câu) | |
| Hybrid Recall@1 test | ghi số | 87.2% | 5 câu rank 2–3, vẫn trong top-5 |
| Hybrid MRR test | ghi số | 0.927 | |
| Dense-only Recall@5 test | so sánh | 94.9% | hybrid thắng |
| Tenant leak `other_department` | 0 hit | 0 failure | 2 fixture |
| Thời hạn ĐHCQ / SĐH / điểm I | đúng TL | 10/10 R@5 | mục 5.1 |
| Threshold | số liệu cal | 0.4167 | nửa score R@1 yếu nhất trên cal |

Baseline metrics dùng `score_threshold=0.0`. Threshold 0.4167 ghi nhận cho Phase 6, chưa áp lên test set.

### 5.1. Câu hỏi thời hạn

| Case | Split | Rank | R@5 |
|---|---|---:|---:|
| para-phuc-khao-dhcq (2 ngày, TL02) | calibration | 1 | 1 |
| para-phuc-khao-sdh (7 ngày, TL02) | test | 1 | 1 |
| para-diem-i-nop (3 ngày, TL03) | calibration | 1 | 1 |
| para-diem-i-hieu-luc (1 năm, TL03) | test | 1 | 1 |
| para-tra-diem-i (7 ngày, TL04) | calibration | 1 | 1 |
| doc-tl02-thoi-han-dhcq | calibration | 2 | 1 |
| doc-tl02-thoi-han-sdh | test | 2 | 1 |
| doc-tl03-ba-ngay | test | 3 | 1 |
| doc-tl03-mot-nam | calibration | 1 | 1 |
| doc-tl04-bay-ngay | calibration | 1 | 1 |

### 5.2. Hybrid vs dense-only Recall@5

| Split | Hybrid | Dense-only |
|---|---:|---:|
| test | 1.000 | 0.949 |
| calibration | 1.000 | 0.983 |
| all | 1.000 | 0.969 |

7 câu retrieval không đứng hạng 1 nhưng đều nằm trong top-5: `doc-tl01-dien-thoai`, `doc-tl02-thoi-han-dhcq`, `doc-tl02-thoi-han-sdh`, `doc-tl02-vb2`, `doc-tl03-ba-ngay`, `para-seb-su-co`, `para-xem-diem`.

Policy/adversarial không tính Recall; chúng khóa hành vi Phase 6 (OOS, handoff, insufficient_evidence, jailbreak).

## 6. Exit gate

| Điều kiện | Kết quả | Ghi chú |
|---|---|---|
| ≥ 80 câu evaluation | Pass | 115 tổng, 97 retrieval |
| Recall@5 sơ bộ ≥ 85% | Pass | test 100%, all 100% |
| Không tenant leakage | Pass | 0/2 fixture |
| Thời hạn theo hệ đào tạo đúng tài liệu | Pass | 10/10 |
| Threshold bằng số liệu, không cảm tính | Pass | 0.4167 từ calibration |

## 7. Quyết định

| ID | Quyết định | Lý do |
|---|---|---|
| DEC-P5-01 | FAQ verbatim từ Silver; paraphrase không dùng exact match | Exact SQL là Phase 6 |
| DEC-P5-02 | Split FAQ theo `sha256(code)[0] % 3`; authored gán tay | Tách cal/test ổn định |
| DEC-P5-03 | Giữ hybrid BGE-M3; dense-only chỉ để so sánh | Hybrid R@5 test 100% vs 94.9% |
| DEC-P5-04 | `top_k=5`; threshold 0.4167 ghi nhận, chưa cắt baseline | Không tối ưu trên test đã đóng băng |
| DEC-P5-05 | Đóng băng `dataset_sha256=1423dd9acfb2087e715880edeb19e9ffed780967b55258f52bcfca3f35ff1f52` | P5.13 |

## 8. Blocker và ngoại lệ

| ID | Nội dung | Owner | Hạn xử lý | Ảnh hưởng |
|---|---|---|---|---|
| — | Không có blocker | — | — | — |

Policy cases chưa có gold label retrieval; Phase 6 graph mới chấm OOS/handoff/insufficient. Contact YAML vẫn `verified: false`.

## 9. Rủi ro chuyển Phase 6

- Recall@5 = 100% trên 97 câu; generation/citation/evidence gate chưa đo.
- Threshold 0.4167 có thể loại hit hạng 3–5 nếu áp ngay — cần kiểm lại trên calibration trước khi cắt.
- Host CLI vẫn phải `POSTGRES_HOST=localhost` và `QDRANT_URL=http://localhost:6333`.
- Dataset hash đổi nếu FAQ Silver đổi nội dung câu hỏi.

## 10. Kết luận

**Kết quả: `ACCEPTED`**

Phase 5 đã đóng bộ đánh giá 115 câu, hybrid Recall@5 = 100% trên test đã đóng băng, không tenant leak, thời hạn ĐHCQ/SĐH/điểm I lấy đúng TL02–TL04. Phase 6 có thể bắt đầu: LangGraph RAG agent.
