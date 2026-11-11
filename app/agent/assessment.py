"""Assessment profile extension; never applied to generic modules."""

from typing import Any

from app.agent.citation import citations_from_evidence
from app.agent.models import RetrievedEvidence
from app.agent.templates import INSUFFICIENT_ANSWER


def apply_evidence_policy(state: dict[str, Any], evidence: list[RetrievedEvidence]) -> bool:
    if state.get("training_system") == "vb2_vlvh":
        topic = state.get("topic")
        if topic == "phuc_khao" and not any(
            item.document_code == "TL02"
            and (
                "vb2" in item.stair_markdown.casefold() or "vlvh" in item.stair_markdown.casefold()
            )
            for item in evidence
        ):
            state["status"] = "insufficient_evidence"
            state["answer"] = (
                "Chưa có dữ liệu đã duyệt về quy trình phúc khảo riêng cho hệ VB2/VLVH. "
                "Bạn vui lòng liên hệ Phòng Bảo đảm chất lượng để được hướng dẫn."
            )
            state["next_node"] = "format_response"
            return True
        if topic in {"diem_i_nhan", "diem_i_tra"}:
            code = "TL04" if topic == "diem_i_tra" else "TL03"
            relevant = [
                item
                for item in evidence
                if item.document_code == code
                and "vb2" in item.stair_markdown.casefold()
                and "phòng đào tạo" in item.stair_markdown.casefold()
            ]
            if relevant:
                state["status"] = "answered"
                if topic == "diem_i_tra":
                    state["answer"] = (
                        "Người học hệ VB2/VLVH thực hiện thủ tục trả điểm I qua "
                        "Phòng Đào tạo. Nguồn: TL04."
                    )
                else:
                    state["answer"] = (
                        "Người học hệ VB2/VLVH nộp đơn xin hoãn thi, nhận điểm I "
                        "trực tiếp tại Phòng Đào tạo. Nguồn: TL03."
                    )
                state["citations"] = [
                    item.model_dump() for item in citations_from_evidence(relevant[:1])
                ]
            else:
                state["status"] = "insufficient_evidence"
                state["answer"] = INSUFFICIENT_ANSWER
            state["next_node"] = "format_response"
            return True
    return False
