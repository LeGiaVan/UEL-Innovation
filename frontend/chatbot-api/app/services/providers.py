from typing import Protocol

from app.services.catalog import CATALOG


class AnswerProvider(Protocol):
    def answer(self, department: str, mode: str, message: str) -> str: ...


class StubAnswerProvider:
    """No LLM, document retrieval, or business request execution yet."""

    def answer(self, department, mode, message):
        if message.strip().casefold().rstrip("!.,? ") in {"hello", "hi", "xin chào"}:
            return (
                f"Xin chào, đây là chatbot {CATALOG[department]['name']} "
                "của Trường Đại học Kinh tế - Luật (UEL). "
                "Tôi có thể hỗ trợ bạn tìm hiểu thông tin và giải đáp các câu hỏi của phòng. "
                "Đây là phản hồi dummy từ backend để kiểm thử API, chưa kết nối LLM."
            )
        topic = CATALOG[department]["topics"][int(mode.split("_")[1]) - 1]
        if message == topic[2]:
            return "[Phản hồi mô phỏng] " + topic[3]
        return f"[Phản hồi mô phỏng] {CATALOG[department]['name']} đã nhận câu hỏi trong phiên chat về {topic[0].lower()}. Hệ thống chưa kết nối tài liệu hoặc LLM và chưa tạo yêu cầu nghiệp vụ."
