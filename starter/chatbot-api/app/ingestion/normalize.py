from __future__ import annotations

import re
import unicodedata
from datetime import date as date_cls
from datetime import datetime


def nfc(value: object) -> str:
    if value is None:
        return ""
    return unicodedata.normalize("NFC", str(value)).strip()


def nfc_lower(value: object) -> str:
    return nfc(value).lower()


def slug(text: str) -> str:
    folded = nfc_lower(text).replace("đ", "d")
    folded = "".join(
        ch for ch in unicodedata.normalize("NFD", folded) if unicodedata.category(ch) != "Mn"
    )
    folded = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    return folded or "chu-de"


def fold_key(value: object) -> str:
    folded = nfc_lower(value).replace("đ", "d")
    folded = "".join(
        ch for ch in unicodedata.normalize("NFD", folded) if unicodedata.category(ch) != "Mn"
    )
    folded = re.sub(r"[^a-z0-9]+", " ", folded)
    return re.sub(r"\s+", " ", folded).strip()


def fold_tokens(value: object) -> set[str]:
    return {tok for tok in fold_key(value).split() if tok}


def normalize_question(text: str) -> str:
    s = nfc_lower(text)
    s = re.sub(r"^[\s.,;:!?…\-–—]+", "", s)
    s = re.sub(r"[\s.,;:!?…\-–—]+$", "", s)
    return re.sub(r"\s+", " ", s)


def skip_sheet(name: str) -> bool:
    n = nfc_lower(name)
    if n.startswith("0.") or n.startswith("_ds"):
        return True
    return n in {"hướng dẫn", "_ds", "mẫu"}


def in_ds(value: str, allowed: set[str]) -> bool:
    if not value:
        return True
    if not allowed:
        return True
    if value in allowed:
        return True
    low = nfc_lower(value)
    if any(nfc_lower(item) == low for item in allowed):
        return True
    folded = fold_key(value)
    return any(fold_key(item) == folded for item in allowed)


_ALIASES: tuple[tuple[str, str], ...] = (
    ("sinh vien dai hoc chinh quy vua lam vua hoc tu xa", "Sinh viên (mọi hệ)"),
    ("sinh vien dai hoc chinh quy vua lam vua hoc", "Sinh viên (mọi hệ)"),
    ("sinh vien moi he", "Sinh viên (mọi hệ)"),
    ("tat ca sinh vien", "Sinh viên (mọi hệ)"),
    ("sv dhcq", "Sinh viên đại học chính quy"),
    ("dhcq", "Sinh viên đại học chính quy"),
    ("sinh vien dai hoc", "Sinh viên đại học chính quy"),
    ("vlvh", "Sinh viên vừa làm vừa học"),
    ("vua lam vua hoc", "Sinh viên vừa làm vừa học"),
    ("van bang 2", "Sinh viên văn bằng 2 / liên thông"),
    ("lien thong", "Sinh viên văn bằng 2 / liên thông"),
    ("lien ket quoc te", "Sinh viên liên kết quốc tế"),
    ("sau dai hoc", "Sau đại học (cao học + nghiên cứu sinh)"),
    ("sdh", "Sau đại học (cao học + nghiên cứu sinh)"),
    ("cao hoc", "Học viên cao học"),
    ("hoc vien", "Học viên cao học"),
    ("nghien cuu sinh", "Nghiên cứu sinh"),
    ("ncs", "Nghiên cứu sinh"),
    ("cuu sinh vien", "Cựu sinh viên"),
    ("phu huynh", "Phụ huynh"),
    ("thi sinh", "Thí sinh / người dự tuyển"),
    ("nguoi du tuyen", "Thí sinh / người dự tuyển"),
    ("doanh nghiep", "Doanh nghiệp / đối tác"),
    ("doi tac", "Doanh nghiệp / đối tác"),
    ("giang vien", "Giảng viên / cán bộ"),
    ("can bo", "Giảng viên / cán bộ"),
    ("tat ca nguoi hoc", "Tất cả người học"),
    ("tat ca", "Tất cả người học"),
    ("han chot", "Hạn chót"),
    ("deadline", "Hạn chót"),
    ("su kien", "Sự kiện"),
    ("event", "Sự kiện"),
    ("dinh ky", "Định kỳ"),
    ("recurring", "Định kỳ"),
    ("bat dau ket thuc", "Bắt đầu - kết thúc"),
    ("khoang thoi gian", "Bắt đầu - kết thúc"),
    ("portal", "Cổng thông tin MyUEL / Portal"),
    ("myuel", "Cổng thông tin MyUEL / Portal"),
    ("cong thong tin", "Cổng thông tin MyUEL / Portal"),
    ("email", "Email"),
    ("truc tuyen", "Trực tuyến"),
    ("online", "Trực tuyến"),
    ("dien thoai", "Điện thoại"),
    ("phone", "Điện thoại"),
    ("truc tiep", "Trực tiếp"),
)


def _item_by_fold(allowed: set[str], folded: str) -> str | None:
    for item in allowed:
        if fold_key(item) == folded:
            return item
    return None


def _is_student_label(item: str) -> bool:
    key = fold_key(item)
    return key.startswith("sinh vien") or key.startswith("hoc vien") or key.startswith("nghien cuu") or key.startswith(
        "sau dai hoc"
    )


def _pick_from_matches(matches: list[str], allowed: set[str]) -> str:
    unique: list[str] = []
    seen: set[str] = set()
    for item in matches:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    if len(unique) == 1:
        return unique[0]
    if unique and all(_is_student_label(item) for item in unique):
        broad = _item_by_fold(allowed, "sinh vien moi he")
        if broad:
            return broad
    mixed = unique and not all(_is_student_label(item) for item in unique)
    if mixed:
        everyone = _item_by_fold(allowed, "tat ca nguoi hoc")
        if everyone:
            return everyone
    return max(unique, key=lambda item: (len(fold_tokens(item)), len(item)))


def _alias_match(folded: str, allowed: set[str]) -> str | None:
    padded = f" {folded} "
    hits: list[tuple[int, str]] = []
    for alias, canonical in _ALIASES:
        if folded == alias or padded.find(f" {alias} ") >= 0:
            item = _item_by_fold(allowed, fold_key(canonical)) or (canonical if canonical in allowed else None)
            if item:
                hits.append((len(alias), item))
    if not hits:
        return None
    hits.sort(reverse=True)
    return hits[0][1]


def resolve_ds(value: str, allowed: set[str]) -> tuple[str, str]:
    raw = nfc(value)
    if not raw:
        return "", "unmatched"
    if not allowed:
        return raw, "exact"
    if raw in allowed:
        return raw, "exact"
    folded = fold_key(raw)
    exact = _item_by_fold(allowed, folded)
    if exact:
        return exact, "exact" if nfc_lower(exact) == nfc_lower(raw) else "mapped"
    tokens = fold_tokens(raw)
    contained: list[str] = []
    for item in allowed:
        item_tokens = fold_tokens(item)
        if len(item_tokens) < 2:
            continue
        if item_tokens <= tokens:
            contained.append(item)
    if contained:
        picked = _pick_from_matches(contained, allowed)
        return picked, "mapped"
    aliased = _alias_match(folded, allowed)
    if aliased:
        return aliased, "mapped"
    return raw, "unmatched"


_VN_DATE = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.IGNORECASE)
_DMY = re.compile(r"(?<!\d)(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})(?!\d)")
_YMD = re.compile(r"(?<!\d)(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})(?!\d)")


def _full_year(year: int) -> int:
    if year < 100:
        return 2000 + year if year < 70 else 1900 + year
    return year


def _iso_date(day: int, month: int, year: int) -> str:
    try:
        return date_cls(_full_year(year), month, day).isoformat()
    except ValueError:
        return ""


def extract_iso_dates(text: object) -> list[str]:
    blob = nfc(text)
    if not blob:
        return []
    found: list[tuple[int, str]] = []
    for match in _VN_DATE.finditer(blob):
        iso = _iso_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if iso:
            found.append((match.start(), iso))
    for match in _DMY.finditer(blob):
        iso = _iso_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if iso:
            found.append((match.start(), iso))
    for match in _YMD.finditer(blob):
        iso = _iso_date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        if iso:
            found.append((match.start(), iso))
    found.sort()
    out: list[str] = []
    seen: set[str] = set()
    for _, iso in found:
        if iso not in seen:
            seen.add(iso)
            out.append(iso)
    return out


def parse_date_value(value: object) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date_cls):
        return value.isoformat()
    if isinstance(value, (int, float)) and 20000 < float(value) < 80000:
        try:
            from openpyxl.utils.datetime import from_excel

            parsed = from_excel(value)
            if isinstance(parsed, datetime):
                return parsed.date().isoformat()
        except Exception:  # noqa: BLE001
            pass
    raw = nfc(value).replace(".", "/")
    if not raw:
        return ""
    if " " in raw:
        raw = raw.split()[0]
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw[:10] if len(raw) >= 8 else raw, fmt).date().isoformat()
        except ValueError:
            continue
    found = extract_iso_dates(nfc(value))
    return found[0] if found else ""


def looks_like_contact(value: str) -> bool:
    text = nfc_lower(value)
    if not text:
        return False
    if "@" in text or text.startswith("http://") or text.startswith("https://") or text.startswith("www."):
        return True
    digits = re.sub(r"\D", "", text)
    return len(digits) >= 8
