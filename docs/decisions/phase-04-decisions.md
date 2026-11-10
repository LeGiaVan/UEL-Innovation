# Phase 4 Decision Record

Ngày chốt: 2026-11-10.

Các quyết định dưới đây khóa Gold Layer trước khi triển khai. Không mở lại trừ khi có quyết định mới.

## DR-P4-01 — Phạm vi index Qdrant

**Trạng thái:** Accepted

Index:

- FAQ (71, kể cả FAQ thiếu văn bản căn cứ ở development).
- Section/procedure/dossier/step của TL01–TL04.

Không index routing rules. Routing phục vụ phân loại phạm vi ở Phase 6, không phải bằng chứng trả lời.

## DR-P4-02 — Exact match rồi vector, FAQ được ưu tiên

**Trạng thái:** Accepted

Thứ tự retrieval (Phase 6 dùng, Phase 4 cung cấp search Gold):

1. Exact match SQL trên `normalized_question` (câu trùng sau chuẩn hóa).
2. Nếu không khớp: hybrid search Qdrant (dense + sparse, fusion RRF) trên một collection.
3. Điểm FAQ được cộng boost trước khi xếp hạng cuối; tài liệu không bị loại nếu FAQ yếu.

Exact match không phải full-text SQL. Câu paraphrase đi qua vector.

## DR-P4-03 — Một collection, `entity_type` trên payload

**Trạng thái:** Accepted

Collection: `uel_knowledge` (test: `uel_knowledge_test`).

`entity_type`: `faq` | `regulation` | `condition` | `procedure` | `dossier` | `step`.

## DR-P4-04 — Chunk STAIR

**Trạng thái:** Accepted

Một Silver section ≈ một chunk. Điều kiện, ngoại lệ, lệ phí, thời hạn gắn vào chunk chủ đề — không tạo chunk chỉ chứa một con số.

FAQ DATA-05 được index ở development; UAT chỉ khi release `approved_for_uat`.

STAIR không chứa contact, email, hotline hay secret.

## DR-P4-05 — Embedding BGE-M3 dense + sparse

**Trạng thái:** Accepted

Model: `BAAI/bge-m3`, CPU, dense 1024 + sparse lexical.

Fusion: Reciprocal Rank Fusion trên Qdrant. Cross-encoder rerank để Phase 5/6.

Không benchmark `e5-base` trừ khi BGE-M3 không chạy được trên máy PoC.

## DR-P4-06 — Ai được index, lọc lúc query

**Trạng thái:** Accepted

Index: `is_active` và `release_status` được phép với môi trường.

`effective_from` / `effective_to` nằm payload; lọc lúc query. Không suy ra ngày hiệu lực từ ngày tạo file.

## DR-P4-07 — Sync Silver rồi Gold; rebuild từ PostgreSQL

**Trạng thái:** Accepted

`python -m app.cli sync` (không `--dry-run`) ghi Bronze + Silver + Gold.

`python -m app.cli rebuild-gold` xóa vector của tenant rồi index lại từ PostgreSQL.

Qdrant lỗi sau khi Silver commit: `sync_runs.status=partial_failed`. Không rollback Silver.

Dry-run không ghi Qdrant.

## DR-P4-08 — Lưu STAIR

**Trạng thái:** Accepted

Payload Qdrant + file Markdown `reports/gold/` (gitignored).

## DR-P4-09 — Chạy embedding trên host CLI

**Trạng thái:** Accepted

Giống Phase 3: host Windows, `QDRANT_URL=http://localhost:6333`.
