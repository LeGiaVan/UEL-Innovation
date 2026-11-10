# Báo cáo Phase 6 — LangGraph RAG agent

## 1. Metadata

| Thuộc tính | Giá trị |
|---|---|
| Phase | 6 |
| Trạng thái | `ACCEPTED` |
| Ngày bắt đầu | 2026-11-10 |
| Ngày kết thúc | 2026-11-10 |
| Phạm vi | Phòng Bảo đảm chất lượng / Mô-đun Khảo khí |
| `department_id` | `bao_dam_chat_luong` |
| `module_code` | `khao_khi` |
| Người thực hiện | Lê Gia Văn / dự án UEL Innovation |
| Commit/Tag | Working tree Phase 6 (chưa commit) |

## 2. Mục tiêu

- Graph LangGraph: normalize → adversarial → routing → FAQ / OOS / handoff / RAG.
- FAQ exact không gọi generation. OOS không gọi Qdrant/generation.
- Handoff không trả dữ liệu cá nhân. Lệ phí unknown abstain. Citation rule.
- LLM qua interface (live: Groq; tùy chọn Gemini); unit test FakeLLM. Timeout 45s; retry 5xx, không retry 429/503/504.
- CLI `chat` in status, citation, latency từng node.

## 3. Checklist hoàn thành

- [x] P6.01–P6.08 — State, normalize, routing, FAQ SQL, metadata enum, retrieve + filter, evidence gate.
- [x] P6.09–P6.12 — LLM interface, system prompt tiếng Việt, cấm kiến thức ngoài context, generate.
- [x] P6.13–P6.16 — Citation rule, insufficient_evidence, human_handoff, out_of_scope.
- [x] P6.17–P6.18 — Timeout/retry, latency từng node.
- [x] P6.19–P6.20 — Graph unit tests + regression policy/adversarial từ `evaluation/cases.yaml`.

## 4. Deliverables

| Deliverable | Đường dẫn | Trạng thái |
|---|---|---|
| Quyết định Phase 6 | `docs/decisions/phase-06-decisions.md` | Hoàn thành |
| Agent package | `app/agent/` | Hoàn thành |
| CLI | `python -m app.cli chat` | Hoàn thành |
| Tests | `tests/unit/test_agent_graph.py`, `test_agent_rules.py` | Hoàn thành |

## 5. Kết quả kiểm tra

| Kiểm tra | Kỳ vọng | Kết quả | Evidence |
|---|---|---|---|
| FAQ exact | không generate, không Qdrant | Pass | `test_faq_exact_does_not_call_generate_or_search` |
| Out-of-scope | không Qdrant, không generate | Pass | học phí / TKB / SEB cài / LMS |
| Handoff | không dữ liệu cá nhân | Pass | MSSV, khiếu nại, cấm thi, không có tên |
| Lệ phí unknown | abstain | Pass | không nêu số tiền, không generate |
| Adversarial | refuse, không LLM | Pass | jailbreak / SQLi / prompt leak |
| Citation sai | insufficient_evidence | Pass | generate không có mã retrieved |
| Timeout generate | status error kiểm soát | Pass | FakeLLM `LlmTimeoutError` |
| Routing LLM fail | answer_allowed rồi RAG | Pass | `llm_default` |
| Clarification ĐHCQ | hỏi lại, lượt 2 retrieve | Pass | MemorySaver `conversation_id` |
| Policy YAML | 11 policy + 5 adversarial | Pass | `test_policy_and_adversarial_cases_from_yaml` |
| pytest unit | xanh | 58 passed | gồm Phase 0–6 |

Retrieval Recall@5 Phase 5 không đụng code search (chỉ `faq_boost` public). Không chạy lại BGE-M3 live trong Phase 6.

## 6. Exit gate

| Điều kiện | Kết quả | Ghi chú |
|---|---|---|
| FAQ match không gọi generation LLM | Pass | |
| OOS không gọi Qdrant hoặc generation | Pass | |
| Handoff không trả dữ liệu cá nhân | Pass | |
| Mọi câu RAG có citation hợp lệ | Pass | fail → insufficient_evidence |
| Lệ phí chưa xác định abstain | Pass | |
| Provider timeout lỗi kiểm soát | Pass | |
| Regression không giảm ngoài ngưỡng | Pass | policy/adversarial YAML; retrieval giữ Phase 5 |

## 7. Quyết định

Xem `docs/decisions/phase-06-decisions.md` (DR-P6-01 … DR-P6-11).

## 8. Blocker và ngoại lệ

| ID | Nội dung | Owner | Hạn xử lý | Ảnh hưởng |
|---|---|---|---|---|
| — | Smoke Groq live phụ thuộc `LLM_API_KEY` trên máy host | Dev | Khi có key | CLI `chat` với `LLM_PROVIDER=groq` |

MemorySaver in-process: tắt CLI mất hội thoại. PostgreSQL checkpointer để Phase 7.

## 9. Rủi ro chuyển Phase 7

- Graph chưa có HTTP; FastAPI phải inject `department_id` server-side, không nhận tenant từ client.
- Groq model chưa khóa tên — đọc `LLM_MODEL` (mặc định `openai/gpt-oss-20b`).
- Keyword routing có thể miss paraphrase OOS; fallback LLM classifier.
- Web chat phải escape HTML (P7.15).

## 10. Kết luận

**Kết quả: `ACCEPTED`**

Phase 6 đã có LangGraph agent với FakeLLM tests phủ FAQ, OOS, handoff, lệ phí, adversarial, citation, timeout và clarification nhiều lượt. Phase 7 có thể bắt đầu: FastAPI, API key và web chat.
