from __future__ import annotations

from typing import Literal

Severity = Literal["error", "warning", "info"]
SourceType = Literal["xlsx", "google-sheets"]
WorkbookRole = Literal["module_and_routing", "faq", "business_documents"]

ROUTING_SCOPE_MAP: dict[str, str] = {
    "Trong phạm vi trả lời": "answer_allowed",
    "Trong phạm vi - bot không tự trả lời & cần cán bộ hỗ trợ": "human_required",
    "Ngoài phạm vi trả lời": "out_of_scope",
}

CONDITION_TYPE_MAP: dict[str, str] = {
    "Điều kiện": "condition",
    "Ngoại lệ": "exception",
    "Lỗi thường gặp": "common_error",
    "Lưu ý": "note",
}

PROCESSING_TIME_MAP: dict[str, str] = {
    "Trong ngày": "same_day",
    "N ngày làm việc": "working_days",
    "Tùy trường hợp": "case_by_case",
}

REQUIRED_FLAG_MAP: dict[str, bool] = {
    "Có": True,
    "Không": False,
}

UNKNOWN_FEE_MARKER = "chưa xác định"
CANONICAL_DEPARTMENT_NAME = "Phòng Bảo đảm chất lượng"
CANONICAL_MODULE_NAME = "Mô-đun Khảo khí"
MODULE_NAME_TOKEN = "Khảo khí"

SKIP_DOCUMENT_SHEETS = frozenset({"Hướng dẫn", "MẪU", "_DS"})
