from __future__ import annotations

from app.ingestion.contact import ResolvedContact

ADVERSARIAL_ANSWER = (
    "Yêu cầu này không được hỗ trợ. Tôi chỉ trả lời quy định khảo thí đã được duyệt "
    "trong dữ liệu của mô-đun Khảo khí."
)

OUT_OF_SCOPE_ANSWER = (
    "Câu hỏi này nằm ngoài phạm vi mô-đun Khảo khí (Phòng Bảo đảm chất lượng). "
    "Vui lòng liên hệ đơn vị phụ trách phù hợp: đào tạo (học phần/thời khóa biểu), "
    "tài chính (học phí/công nợ), hoặc hỗ trợ kỹ thuật (cài đặt phần mềm, đăng nhập hệ thống)."
)

CLARIFICATION_ANSWER = (
    "Bạn đang hỏi thời hạn theo quy định khảo thí. Vui lòng cho biết hệ đào tạo: "
    "đại học chính quy (ĐHCQ), sau đại học (SĐH), hoặc VB2/vừa làm vừa học (VLVH)."
)


def scope_clarification_answer(
    *,
    module_name: str,
    related_faqs: list[str] | None = None,
) -> str:
    lines = [
        f"Tôi chưa đủ căn cứ để trả lời chắc câu hỏi này trong **{module_name}**.",
        "",
        "Bạn hãy bổ sung **một** ý cụ thể:",
        "- Thủ tục bạn cần (phúc khảo, điểm I, hình thức thi, …)",
        "- Hệ đào tạo nếu hỏi thời hạn: **ĐHCQ** (đại học chính quy), "
        "**SĐH** (sau đại học), hoặc **VB2/VLVH**",
        "- Hoặc đây là hồ sơ/điểm của một người — khi đó cần cán bộ hỗ trợ",
    ]
    faqs = [item.strip() for item in (related_faqs or []) if item.strip()][:3]
    if faqs:
        lines += ["", "Nếu đúng một trong các câu này, gửi lại nguyên câu:"]
        lines += [f"- {question}" for question in faqs]
    return "\n".join(lines)

INSUFFICIENT_ANSWER = (
    "Chưa đủ dữ liệu đã được duyệt để trả lời chắc chắn. "
    "Tôi không nêu mức lệ phí hoặc kết luận ngoài nguồn."
)

FEE_UNKNOWN_ANSWER = (
    "Nguồn đã duyệt ghi lệ phí chưa xác định. Tôi không nêu số tiền. "
    "Vui lòng liên hệ đơn vị khảo thí để được hướng dẫn mức thu hiện hành."
)

TIMEOUT_ANSWER = (
    "Hệ thống tạm thời không gọi được mô hình ngôn ngữ. Vui lòng thử lại sau."
)

PROVIDER_ERROR_ANSWER = (
    "Không đọc được câu trả lời từ mô hình. Vui lòng thử lại hoặc hỏi một quy định khảo thí cụ thể."
)

GREETING_ANSWER = (
    "Xin chào. Tôi là trợ lý mô-đun Khảo khí, Phòng Bảo đảm chất lượng (UEL). "
    "Bạn có thể hỏi quy định thi, phúc khảo, điểm I hoặc hình thức thi. "
    "Tôi không trả lời học phí, thời khóa biểu, hay hồ sơ/điểm của một người học cụ thể."
)

HANDOFF_NO_FAQ = (
    "Tôi không kết luận hồ sơ, điểm số hoặc kết quả của một người học cụ thể. "
    "Vui lòng liên hệ cán bộ phụ trách để được hỗ trợ."
)


def with_contact(body: str, contact: ResolvedContact | None) -> str:
    if contact is None:
        return body
    parts = [
        contact.support_contact,
        contact.contact_information,
        contact.online_channel,
    ]
    filled = [item for item in parts if item]
    if not filled:
        return body
    return f"{body}\n\nĐầu mối hỗ trợ: {' | '.join(filled)}"
