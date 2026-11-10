from __future__ import annotations

from app.agent.models import AgentTopic, TrainingSystem

_DHCQ = ("đại học chính quy", "dai hoc chinh quy", "đhcq", "dhcq", "chính quy")
_SDH = ("sau đại học", "sau dai hoc", "sđh", "sdh", "cao học", "cao hoc", "thạc sĩ", "thac si")
_VB2 = ("vb2", "văn bằng 2", "van bang 2", "vlvh", "vừa làm vừa học", "vua lam vua hoc")

_FEE = ("lệ phí", "le phi", "bao nhiêu đồng", "mức thu", "mat phi", "mất phí")
_PHUC_KHAO = ("phúc khảo", "phuc khao")
_DIEM_I = ("điểm i", "diem i")
_TRA_DIEM = ("trả điểm i", "tra diem i", "thi bổ sung", "thi bo sung")
_DEADLINE = (
    "thời hạn",
    "thoi han",
    "mấy ngày",
    "may ngay",
    "bao lâu",
    "bao lau",
    "bao nhiêu ngày",
    "hiệu lực",
    "hieu luc",
    "quá hạn",
    "qua han",
    "trước hạn",
    "truoc han",
    "trước đợt",
    "truoc dot",
    "trước 7 ngày",
    "trong mấy ngày",
    "trong 3 ngày",
    "01 năm",
    "1 năm",
)


def detect_training_system(text: str) -> TrainingSystem:
    folded = text.casefold()
    if any(token in folded for token in _VB2):
        return "vb2_vlvh"
    if any(token in folded for token in _SDH):
        return "sdh"
    if any(token in folded for token in _DHCQ):
        return "dhcq"
    return "unknown"


def detect_topic(text: str) -> AgentTopic:
    folded = text.casefold()
    if any(token in folded for token in _FEE):
        return "fee"
    if any(token in folded for token in _TRA_DIEM):
        return "diem_i_tra"
    if any(token in folded for token in _DIEM_I):
        return "diem_i_nhan"
    if any(token in folded for token in _PHUC_KHAO):
        return "phuc_khao"
    if "seb" in folded or "safe exam" in folded:
        return "seb"
    if "hình thức thi" in folded or "hinh thuc thi" in folded:
        return "hinh_thuc_thi"
    return "other"


def is_fee_question(text: str) -> bool:
    return detect_topic(text) == "fee"


def is_deadline_question(text: str) -> bool:
    folded = text.casefold()
    topic = detect_topic(text)
    if topic not in {"phuc_khao", "diem_i_nhan", "diem_i_tra"}:
        return False
    return any(token in folded for token in _DEADLINE)


def needs_training_system_clarification(text: str) -> bool:
    if detect_training_system(text) != "unknown":
        return False
    return is_deadline_question(text)
