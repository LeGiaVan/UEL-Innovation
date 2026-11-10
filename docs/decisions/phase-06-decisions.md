# Phase 6 Decision Record

Ngày chốt: 2026-11-10.

Các quyết định dưới đây khóa LangGraph RAG agent trước khi triển khai. Không mở lại trừ khi có quyết định mới.

## DR-P6-01 — FAQ match chỉ exact normalized

**Trạng thái:** Accepted

Exact match SQL trên `normalized_question` (NFC, lowercase, trim, bỏ dấu câu đầu/cuối, giữ dấu tiếng Việt).

Không bảng alias. Không fuzzy. Không LLM cho FAQ match.

Khớp → trả nguyên văn FAQ, status `faq_answered`, không gọi generation LLM.

Paraphrase (Phase 5 `exact_match_eligible: false`) đi routing → RAG.

## DR-P6-02 — Routing: keyword trước, LLM classifier khi không khớp

**Trạng thái:** Accepted

17 dòng Silver `scope_type`: `answer_allowed` | `human_required` | `out_of_scope`.

1. Rule/keyword + `topic` / `bot_behavior` (học phí, TKB, MSSV, kết quả cá nhân, cài SEB, …).
2. Không khớp rule → LLM structured output, enum `scope_type` bắt buộc.
3. `out_of_scope` → template, không Qdrant, không generation.
4. Keyword đã OOS/handoff thì không gọi LLM routing.

LLM routing fail (timeout/5xx sau retry): coi như `answer_allowed`, tiếp FAQ/RAG — trừ khi rule đã chốt OOS/handoff.

## DR-P6-03 — human_required: FAQ chung + handoff

**Trạng thái:** Accepted

Nếu routing = `human_required` và exact FAQ khớp: trả FAQ + status `human_handoff` + đầu mối. Không generation, không RAG.

Không khớp FAQ: chỉ handoff, không Qdrant, không generation.

Không trả dữ liệu cá nhân (điểm, MSSV, hồ sơ, khiếu nại riêng).

Contact: inherit module/department; `verified: false` chỉ hiện ở `development`/`test` (giữ Phase 3).

## DR-P6-04 — LLM: Groq (mặc định live), node nào được gọi

**Trạng thái:** Accepted (sửa 2026-11-10: đổi provider live từ Gemini → Groq Cloud)

Provider live: Groq Cloud, OpenAI-compatible `https://api.groq.com/openai/v1`.
Model đọc `LLM_MODEL` từ `.env`. Mặc định: `openai/gpt-oss-20b` (`llama-3.3-70b-versatile` đã shutdown trên Groq free/developer).
`LLM_PROVIDER=groq` | `gemini` | `fake`. Gemini giữ làm fallback. Unit test: FakeLLM, không mạng.

Node gọi LLM:

- Routing fallback (DR-P6-02).
- `metadata_extract`: structured output, enum chặt (hệ đào tạo, chủ đề). Không tự bịa mã TL / question_code.
- `generate`: chỉ từ STAIR/FAQ đã retrieve. Cấm kiến thức ngoài context cho quy định UEL.

Không gọi LLM: FAQ exact, OOS, adversarial refuse, evidence fail, citation fail, handoff không FAQ.

Chỉ gửi câu hỏi + STAIR/FAQ đã duyệt. Không gửi email, hotline, secret, PII.

## DR-P6-05 — Citation verify bằng rule

**Trạng thái:** Accepted

Mọi `question_code` / `document_code` / `chunk_id` nêu trong câu trả lời phải thuộc `retrieved_chunks`.

Sai → `insufficient_evidence`, không generation lại, không LLM verify.

## DR-P6-06 — Evidence gate theo Phase 5

**Trạng thái:** Accepted

Hybrid search, `top_k=5`, cắt `boosted_score < 0.4167`.

Đủ nếu ≥ 1 hit sau cắt. Không đủ → `insufficient_evidence`, không generation.

Lệ phí `fee_type=unknown` (DATA-07): luôn `insufficient_evidence`, cấm nêu số tiền.

## DR-P6-07 — Thiếu hệ đào tạo thì hỏi lại

**Trạng thái:** Accepted

Câu thời hạn (phúc khảo, điểm I, …) không nêu ĐHCQ / SĐH / VB2–VLVH → `clarification_required`. Không retrieve, không generate.

Lượt 2 cùng `conversation_id` mới retrieve.

## DR-P6-08 — Hội thoại nhiều lượt, MemorySaver Phase 6

**Trạng thái:** Accepted

LangGraph `MemorySaver` in-process theo `conversation_id`. Tắt process là mất.

PostgreSQL checkpointer để Phase 7 khi có API. Không làm SqliteSaver.

## DR-P6-09 — Adversarial chặn trước, không LLM

**Trạng thái:** Accepted

Jailbreak, đòi đề thi/đáp án, leak system prompt, SQLi: rule/pattern trước routing.

Status `error` hoặc từ chối template tiếng Việt. Không Qdrant, không LLM.

## DR-P6-10 — Timeout / retry

**Trạng thái:** Accepted

Timeout 45 giây / node LLM (HTTP ≥ 10s; generate RAG cắt 20s rồi trích nguồn).
Retry 1 lần chỉ với 500/502/503. Không retry 504/timeout (cùng prompt sẽ hết hạn lần nữa).
Sau đó `status=error`, không bịa câu.

Routing LLM fail: DR-P6-02.

## DR-P6-11 — CLI chat Phase 6; API/web Phase 7

**Trạng thái:** Accepted

`python -m app.cli chat --department … --module … [--conversation-id]`

In `status`, citation, latency từng node.

Không web chat, không `POST /v1/chat` ở Phase 6. Không `eval-agent` riêng; regression retrieval Phase 5 giữ nguyên.

## Thứ tự graph đã khóa

```text
normalize_input
  → adversarial refuse? → error template
  → routing (keyword → else LLM enum)
      OOS → out_of_scope template
      human_required → FAQ exact? FAQ+handoff : handoff
      answer_allowed → FAQ exact? faq_answered
        → else clarification nếu thiếu hệ (câu thời hạn)
        → metadata_extract (LLM enum)
        → retrieve hybrid + threshold 0.4167
        → evidence_gate / fee unknown
        → generate (LLM)
        → citation rule
        → answered | insufficient_evidence
```
