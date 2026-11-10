from __future__ import annotations

import re

_PATTERNS = (
    re.compile(r"ignore (all )?previous instructions", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"system prompt", re.IGNORECASE),
    re.compile(r"api key", re.IGNORECASE),
    re.compile(r"drop\s+table", re.IGNORECASE),
    re.compile(r"' or 1=1", re.IGNORECASE),
    re.compile(r"or 1=1;?", re.IGNORECASE),
    re.compile(r"--\s*phúc khảo", re.IGNORECASE),
    re.compile(r"đề thi đã có đáp án"),
    re.compile(r"full exam answer key", re.IGNORECASE),
    re.compile(r"bỏ mọi quy định"),
    re.compile(r"bạn là admin"),
    re.compile(r"in ra system prompt"),
    re.compile(r"đáp án cho mọi môn"),
)


def is_adversarial(text: str) -> bool:
    return any(pattern.search(text) for pattern in _PATTERNS)
