from __future__ import annotations

from app.ingestion.excel import (
    KIND_DEADLINE,
    KIND_EVENT,
    KIND_RANGE,
    KIND_RECURRING,
    SCOPE_CODE,
    SCOPE_HANDOFF,
    SCOPE_OOS,
    ParsedBundle,
    parse_bundle,
)
from app.ingestion.issues import IssueLog
from app.ingestion.normalize import extract_iso_dates, in_ds, looks_like_contact, nfc, resolve_ds, slug


def _ds_examples(allowed: set[str], limit: int = 12) -> str:
    items = sorted((item for item in allowed if item), key=str.casefold)
    if len(items) <= limit:
        return ", ".join(items)
    return ", ".join(items[:limit]) + f" … ({len(items)} mục)"


def _canon(
    value: str,
    allowed: set[str],
    issues: IssueLog,
    *,
    file: str,
    label: str,
    ref: str = "",
    required: bool = False,
    strict: bool = False,
) -> str:
    raw = nfc(value)
    if not raw:
        if required:
            issues.error(f"{label} chưa chọn.", file, code="required", ref=ref)
        return ""
    resolved, how = resolve_ds(raw, allowed)
    if how == "exact":
        return resolved
    if how == "mapped":
        issues.warning(
            f"{label}: «{raw}» đã chuẩn hóa thành «{resolved}».",
            file,
            code="ds_mapped",
            ref=ref,
            raw=raw,
            mapped=resolved,
        )
        return resolved
    if strict:
        extra = f" Danh sách chọn: {_ds_examples(allowed)}." if allowed else ""
        issues.error(
            f"{label}: «{raw}» không khớp danh sách chọn.{extra}",
            file,
            code="ds_mismatch",
            ref=ref,
            raw=raw,
        )
        return raw
    extra = f" Danh sách chọn: {_ds_examples(allowed)}." if allowed else ""
    issues.warning(
        f"{label}: «{raw}» không có trong danh sách chọn — giữ nguyên, không chặn nạp.{extra}",
        file,
        code="ds_keep",
        ref=ref,
        raw=raw,
    )
    return raw


def _fill_milestone_dates(ms: dict, issues: IssueLog) -> None:
    if ms.get("start") or ms.get("end"):
        return
    found = extract_iso_dates(" ".join([ms.get("name") or "", ms.get("full_text") or "", ms.get("note") or ""]))
    if not found:
        return
    kind = ms.get("kind") or ""
    ref = ms.get("milestone_id") or ""
    name = ms.get("name") or "mốc"
    if kind == KIND_DEADLINE:
        ms["end"] = found[-1]
        if len(found) > 1:
            ms["start"] = found[0]
    elif kind == KIND_RANGE and len(found) >= 2:
        ms["start"], ms["end"] = found[0], found[-1]
    else:
        ms["start"] = found[0]
    pretty = ", ".join(found)
    issues.warning(
        f"File mốc thời gian {ref} ({name}): không có ngày ở cột Bắt đầu/Kết thúc, "
        f"đã lấy từ nội dung: {pretty}.",
        "04",
        code="date_extracted",
        ref=ref,
        mapped=pretty,
    )


def validate_bundle(bundle: ParsedBundle, *, module_code: str, module_name: str) -> None:
    issues = bundle.issues
    f01 = bundle.file01
    if nfc(f01.module_name) != nfc(module_name):
        issues.error(
            f"Tên Mô-đun File 01 ({f01.module_name!r}) không khớp yaml ({module_name!r})",
            "01",
            code="module_name",
            raw=f01.module_name,
        )
    if not f01.department_name:
        issues.error("File 01 thiếu Phòng ban phụ trách", "01", code="required")
    if not f01.module_description:
        issues.error("File 01 thiếu Mô tả Mô-đun", "01", code="required")
    if not f01.primary_audience:
        issues.error("File phạm vi: chưa chọn Đối tượng phục vụ chính (hàng đầu file).", "01", code="required")
    else:
        f01.primary_audience = _canon(
            f01.primary_audience,
            bundle.ds["audience"],
            issues,
            file="01",
            label="Đối tượng phục vụ chính",
        )
    if not f01.topics:
        issues.error("File 01 cần ≥ 1 dòng chủ đề", "01", code="required")

    slugs: dict[str, str] = {}
    for row in f01.topics:
        topic = row["topic"]
        if not row["stt"]:
            issues.error(f"File 01 chủ đề {topic!r} thiếu STT", "01", code="required", ref=topic)
        if row["scope"] not in SCOPE_CODE:
            issues.error(f"File 01 scope không hợp lệ: {row['scope']!r}", "01", code="scope", ref=topic, raw=row["scope"])
        elif bundle.ds["scope"] and not in_ds(row["scope"], bundle.ds["scope"]):
            issues.error(f"File 01 scope không nằm trong _DS: {row['scope']!r}", "01", code="scope", ref=topic, raw=row["scope"])
        if not row["bot_behavior"]:
            issues.error(f"File 01 chủ đề {topic!r} thiếu cách xử lý", "01", code="required", ref=topic)
        row["audience"] = _canon(
            row["audience"],
            bundle.ds["audience"],
            issues,
            file="01",
            label=f"Chủ đề «{topic}» — đối tượng áp dụng",
            ref=topic,
            required=True,
        )
        key = slug(topic)
        if key in slugs:
            issues.error(f"Trùng slug chủ đề: {key} ({slugs[key]!r} / {topic!r})", "01", code="duplicate", ref=topic)
        slugs[key] = topic
        row["rule_id"] = f"{module_code}.{key}"
        row["scope_code"] = SCOPE_CODE.get(row["scope"], "")
        if row["scope"] in {SCOPE_HANDOFF, SCOPE_OOS}:
            has_local = bool(row["contact_name"] or row["contact_info"] or row["channel"])
            has_default = bool(f01.default_contact_name or f01.default_contact_info)
            if not has_local and not has_default:
                issues.error(f"File 01 chủ đề {topic!r} (handoff/OOS) thiếu đầu mối F/G/H", "01", code="required", ref=topic)
        channel = row.get("channel") or ""
        if channel and looks_like_contact(channel):
            extra = channel
            row["channel"] = ""
            if extra not in (row.get("contact_info") or ""):
                row["contact_info"] = " ".join(x for x in [row.get("contact_info") or "", extra] if x).strip()
            issues.warning(
                f"Chủ đề «{topic}»: email/link ở cột Kênh đã chuyển sang thông tin liên hệ. "
                "Cột Kênh chỉ chọn: Trực tuyến, Email, Cổng thông tin MyUEL / Portal, …",
                "01",
                code="channel_relocated",
                ref=topic,
                raw=extra,
            )
            channel = ""
        if channel:
            row["channel"] = _canon(
                channel,
                bundle.ds["channel"],
                issues,
                file="01",
                label=f"Chủ đề «{topic}» — kênh",
                ref=topic,
            )

    codes: set[str] = set()
    norms: dict[str, str] = {}
    for faq in bundle.faqs:
        code = faq["question_code"]
        if not code:
            issues.error("File 02 thiếu MÃ CÂU HỎI", "02", code="required")
        elif code in codes:
            issues.error(f"File 02 trùng mã {code}", "02", code="duplicate", ref=code)
        codes.add(code)
        if not faq["section"]:
            issues.error(f"File 02 {code} thiếu phân mục", "02", code="required", ref=code)
        if not faq["answer"]:
            issues.error(f"File 02 {code} thiếu câu trả lời", "02", code="required", ref=code)
        faq["audience"] = _canon(
            faq["audience"],
            bundle.ds["audience"],
            issues,
            file="02",
            label=f"Câu hỏi {code} — đối tượng",
            ref=code,
            required=True,
        )
        norm = faq["question_norm"]
        if norm in norms:
            issues.error(f"File 02 trùng câu đã chuẩn hóa: {faq['question']!r}", "02", code="duplicate", ref=code)
        norms[norm] = faq["question"]
    if not bundle.faqs:
        issues.warning("File 02 không có FAQ", "02", code="empty")

    if not bundle.milestones:
        issues.warning("File 04 không có mốc (0 dòng)", "04", code="empty")
    seen_ms: set[str] = set()
    for ms in bundle.milestones:
        mid = ms["milestone_id"]
        name = ms.get("name") or "mốc"
        if not mid:
            issues.error("File 04 thiếu MÃ MỐC", "04", code="required")
        elif mid in seen_ms:
            issues.error(f"File 04 trùng mã {mid}", "04", code="duplicate", ref=mid)
        seen_ms.add(mid)
        if not ms["group"] or not ms["full_text"] or not ms["academic_term"] or not ms["audience"]:
            issues.error(
                f"File 04 {mid} thiếu nhóm/nội dung/học kỳ/đối tượng",
                "04",
                code="required",
                ref=mid,
            )
        ms["audience"] = _canon(
            ms["audience"],
            bundle.ds["audience"],
            issues,
            file="04",
            label=f"Mốc {mid} — đối tượng",
            ref=mid,
        )
        ms["kind"] = _canon(
            ms["kind"],
            bundle.ds["kind"],
            issues,
            file="04",
            label=f"Mốc {mid} ({name}) — loại mốc",
            ref=mid,
            required=True,
        )
        _fill_milestone_dates(ms, issues)
        if ms["kind"] == KIND_DEADLINE and not (ms["end"] or ms["start"]):
            issues.warning(
                f"File mốc thời gian {mid} ({name}): loại Hạn chót chưa có ngày cột Kết thúc — "
                "vẫn nạp; bot sẽ nói theo cột Nội dung. Nên điền 31/12/2026 khi biết ngày.",
                "04",
                code="date_missing",
                ref=mid,
            )
        if ms["kind"] == KIND_RANGE and not (ms["start"] and ms["end"]):
            issues.warning(
                f"File mốc thời gian {mid} ({name}): loại Bắt đầu - kết thúc chưa đủ hai cột ngày — "
                "vẫn nạp; bot sẽ nói theo cột Nội dung.",
                "04",
                code="date_missing",
                ref=mid,
            )
        if ms["kind"] == KIND_EVENT and not (ms["start"] or ms["end"]):
            issues.warning(
                f"File mốc thời gian {mid} ({name}): loại Sự kiện chưa có ngày — "
                "vẫn nạp; bot sẽ nói theo cột Nội dung.",
                "04",
                code="date_missing",
                ref=mid,
            )
        if ms["kind"] == KIND_RECURRING:
            pass

    if not bundle.intro_chunks:
        issues.warning("File 05 không có bài (0 dòng)", "05", code="empty")


def parse_and_validate(files: dict[int, bytes], *, module_code: str, module_name: str) -> ParsedBundle:
    bundle = parse_bundle(files)
    validate_bundle(bundle, module_code=module_code, module_name=module_name)
    return bundle
