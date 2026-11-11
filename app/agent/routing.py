from __future__ import annotations

from app.agent.models import RoutingScope

OOS_KEYWORDS = (
    "học phí",
    "cong no",
    "công nợ",
    "học bổng",
    "thời khóa biểu",
    "thoi khoa bieu",
    "đăng ký học phần",
    "dang ky hoc phan",
    "hủy học phần",
    "không đăng nhập",
    "không dang nhap",
    "lms",
    "kỷ luật",
    "ky luat",
    "công tác sinh viên",
    "phòng đào tạo",
)

SEB_INSTALL_KEYWORDS = (
    "không cài",
    "khong cai",
    "cài được",
    "cai duoc",
    "cài đặt",
    "cai dat",
)

IN_SCOPE_KEYWORDS = (
    "điểm i",
    "diem i",
    "hoãn thi",
    "hoan thi",
    "vắng thi không lý do",
    "vang thi khong ly do",
    "phúc khảo",
    "phuc khao",
    "khảo thí",
    "khao thi",
    "hình thức thi",
    "hinh thuc thi",
    "phòng thi",
    "phong thi",
    "thi bổ sung",
    "thi bo sung",
    "trả điểm",
    "tra diem",
)

HANDOFF_KEYWORDS = (
    "mã số sinh viên",
    "ma so sinh vien",
    "mssv",
    "điểm thi của tôi",
    "diem thi cua toi",
    "kết quả của tôi",
    "ket qua cua toi",
    "của riêng tôi",
    "cua rieng toi",
    "khiếu nại",
    "khieu nai",
    "cấm thi",
    "cam thi",
    "không có tên trong danh sách",
    "khong co ten trong danh sach",
    "hồ sơ cá nhân",
    "ho so ca nhan",
)


GREETING_PHRASES = (
    "xin chào",
    "xin chao",
    "chào bạn",
    "chao ban",
    "chào bot",
    "chào",
    "chao",
    "hello",
    "hi",
    "hey",
    "good morning",
    "good afternoon",
    "cảm ơn",
    "cam on",
    "thanks",
    "thank you",
    "tạm biệt",
    "tam biet",
    "bye",
)

_GREETING_LEFTOVER = frozenset(
    {"", "bạn", "ban", "bot", "assistant", "uel", "ạ", "a", "nhé", "nhe", "nha"}
)


def is_greeting(text: str) -> bool:
    folded = " ".join(text.casefold().split())
    if not folded:
        return False
    remainder = folded
    for phrase in sorted(GREETING_PHRASES, key=len, reverse=True):
        remainder = remainder.replace(phrase, " ")
    leftover = " ".join(remainder.split())
    leftover = leftover.strip(" .,!?。！？")
    return leftover in _GREETING_LEFTOVER


def keyword_scope(text: str) -> RoutingScope | None:
    folded = text.casefold()
    if _is_seb_howto(folded):
        return "answer_allowed"
    if _contains_any(folded, SEB_INSTALL_KEYWORDS) and _mentions_seb(folded):
        return "out_of_scope"
    if _contains_any(folded, OOS_KEYWORDS):
        return "out_of_scope"
    if _contains_any(folded, HANDOFF_KEYWORDS):
        return "human_required"
    if _looks_personal_result(folded):
        return "human_required"
    if _is_general_exam_channel_question(folded):
        return "answer_allowed"
    if _contains_any(folded, IN_SCOPE_KEYWORDS):
        return "answer_allowed"
    return None


def _mentions_seb(text: str) -> bool:
    return "seb" in text or "safe exam" in text


def _is_seb_howto(text: str) -> bool:
    if not _mentions_seb(text):
        return False
    if _contains_any(text, SEB_INSTALL_KEYWORDS):
        return False
    return any(token in text for token in ("cách thức", "cach thuc", "hướng dẫn", "huong dan"))


def _looks_personal_result(text: str) -> bool:
    if "điểm thi" in text or "diem thi" in text or "kết quả phúc khảo" in text:
        if any(token in text for token in ("của tôi", "cua toi", "mssv", "mã số")):
            return True
    return False


def _is_general_exam_channel_question(text: str) -> bool:
    if not _contains_any(text, ("ở đâu", "o dau", "hệ thống nào", "he thong nao")):
        return False
    if _contains_any(
        text,
        ("của tôi", "cua toi", "của em", "cua em", "bị mất", "bi mat", "không thấy", "khong thay"),
    ):
        return False
    return _contains_any(
        text,
        (
            "tra cứu điểm học phần",
            "tra cuu diem hoc phan",
            "nộp tiểu luận",
            "nop tieu luan",
            "nộp báo cáo cuối kỳ",
            "nop bao cao cuoi ky",
        ),
    )


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)
