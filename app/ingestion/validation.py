from __future__ import annotations

from collections import Counter

from app.ingestion.enums import (
    Severity,
)
from app.ingestion.manifest import ReleaseManifest
from app.ingestion.models import (
    CountSummary,
    ExtractionBundle,
    PolicyFinding,
    RawDocument,
    SourceLocation,
    ValidationIssue,
    ValidationReport,
)
from app.ingestion.normalize import (
    extract_emails,
    extract_urls,
    is_valid_http_url,
    looks_like_url,
)


def _issue(
    severity: Severity,
    code: str,
    message: str,
    source: SourceLocation | None = None,
    record_key: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        code=code,
        message=message,
        source_file=source.source_file if source else None,
        source_sheet=source.source_sheet if source else None,
        source_row=source.source_row if source else None,
        source_column=source.source_column if source else None,
        record_key=record_key,
    )


def count_bundle(bundle: ExtractionBundle) -> CountSummary:
    return CountSummary(
        routing_rules=len(bundle.routing_rules),
        faqs=len(bundle.faqs),
        documents=len(bundle.documents),
        regulation_sections=sum(len(item.regulation_sections) for item in bundle.documents),
        condition_exception_sections=sum(len(item.condition_sections) for item in bundle.documents),
        dossier_items=sum(len(item.dossier_items) for item in bundle.documents),
        procedure_steps=sum(len(item.procedure_steps) for item in bundle.documents),
    )


def _validate_urls(
    value: str | None, source: SourceLocation, required: bool
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not value:
        return issues
    urls = extract_urls(value)
    if looks_like_url(value) and not urls:
        urls = [value]
    for url in urls:
        if is_valid_http_url(url):
            continue
        issues.append(
            _issue(
                "error" if required else "warning",
                "INVALID_URL",
                f"URL không hợp lệ: {url}",
                source,
            )
        )
    return issues


def _validate_contacts(value: str | None, source: SourceLocation) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not value:
        return issues
    emails = extract_emails(value)
    if "@" in value and not emails:
        issues.append(_issue("warning", "INVALID_EMAIL", f"Email không hợp lệ: {value}", source))
    issues.extend(_validate_urls(value, source, required=False))
    return issues


def _validate_faqs(bundle: ExtractionBundle) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: Counter[str] = Counter()
    for faq in bundle.faqs:
        if faq.question_code:
            seen[faq.question_code] += 1
        else:
            issues.append(_issue("error", "FAQ_MISSING_CODE", "FAQ thiếu mã câu hỏi.", faq.source))
        if not faq.question:
            issues.append(
                _issue(
                    "error",
                    "FAQ_MISSING_QUESTION",
                    "FAQ thiếu câu hỏi.",
                    faq.source,
                    faq.question_code,
                )
            )
        if not faq.answer:
            issues.append(
                _issue(
                    "error",
                    "FAQ_MISSING_ANSWER",
                    "FAQ thiếu câu trả lời.",
                    faq.source,
                    faq.question_code,
                )
            )
        if not faq.legal_basis:
            issues.append(
                _issue(
                    "warning",
                    "DATA-05",
                    "FAQ chưa có văn bản căn cứ; được phép dùng trong development.",
                    faq.source,
                    faq.question_code,
                )
            )
        if not faq.support_contact and not faq.contact_information and not faq.online_channel:
            pass  # summarized as DATA-06
        issues.extend(_validate_contacts(faq.contact_information, faq.source))
        issues.extend(_validate_urls(faq.online_channel, faq.source, required=False))
    for code, count in seen.items():
        if count > 1:
            issues.append(
                _issue("error", "FAQ_DUPLICATE_CODE", f"Mã FAQ bị trùng: {code}", record_key=code)
            )
    return issues


def _validate_routing(bundle: ExtractionBundle) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for key, count in Counter(rule.source_key for rule in bundle.routing_rules).items():
        if count > 1:
            issues.append(
                _issue("error", "ROUTING_DUPLICATE_ID", "Duplicate rule ID", record_key=key)
            )
    for rule in bundle.routing_rules:
        if not rule.scope_type:
            issues.append(
                _issue(
                    "error",
                    "ROUTING_INVALID_SCOPE",
                    f"Loại phạm vi không hợp lệ: {rule.scope_type_raw}",
                    rule.source,
                    rule.source_key,
                )
            )
        if not rule.topic:
            issues.append(
                _issue("error", "ROUTING_MISSING_TOPIC", "Routing rule thiếu chủ đề.", rule.source)
            )
        issues.extend(_validate_contacts(rule.contact_information, rule.source))
        issues.extend(_validate_urls(rule.online_channel, rule.source, required=False))
    return issues


def _validate_procedure(document: RawDocument) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    procedure = document.procedure
    if procedure is None:
        return issues
    if procedure.processing_time_type == "working_days" and (
        procedure.max_working_days is None or procedure.max_working_days <= 0
    ):
        issues.append(
            _issue(
                "error",
                "INVALID_WORKING_DAYS",
                "Thời hạn 'N ngày làm việc' cần số ngày nguyên dương.",
                procedure.source,
                document.document_code,
            )
        )
    if procedure.fee_type == "unknown":
        issues.append(
            _issue(
                "warning",
                "DATA-07",
                "Lệ phí chưa xác định; cấm nêu số tiền, abstain hoặc handoff.",
                procedure.source,
                document.document_code,
            )
        )
        if procedure.fee_amount_vnd is not None:
            issues.append(
                _issue(
                    "error",
                    "FEE_AMOUNT_FORBIDDEN",
                    "fee_amount_vnd phải null khi fee_type=unknown.",
                    procedure.source,
                    document.document_code,
                )
            )
    issues.extend(_validate_urls(procedure.submission_url, procedure.source, required=False))
    return issues


def _validate_documents(bundle: ExtractionBundle) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for document in bundle.documents:
        if not document.document_code:
            issues.append(
                _issue("error", "DOCUMENT_MISSING_CODE", "Tài liệu thiếu mã.", document.source)
            )
        if not document.title:
            issues.append(
                _issue("error", "DOCUMENT_MISSING_TITLE", "Tài liệu thiếu tên.", document.source)
            )
        if document.document_type is None:
            issues.append(
                _issue(
                    "error",
                    "DOCUMENT_EMPTY",
                    "Tài liệu được duyệt nhưng không có nội dung phân loại được.",
                    document.source,
                    document.document_code,
                )
            )
        for section in document.condition_sections:
            if not section.scenario or not section.resolution:
                issues.append(
                    _issue(
                        "error",
                        "CONDITION_INCOMPLETE",
                        "Điều kiện/ngoại lệ cần cả tình huống và cách xử lý.",
                        section.source,
                        document.document_code,
                    )
                )
            if section.condition_type_raw and section.condition_type is None:
                issues.append(
                    _issue(
                        "error",
                        "CONDITION_INVALID_TYPE",
                        f"Loại điều kiện không hợp lệ: {section.condition_type_raw}",
                        section.source,
                        document.document_code,
                    )
                )
        for item in document.dossier_items:
            if not item.name:
                issues.append(
                    _issue(
                        "error", "DOSSIER_MISSING_NAME", "Hồ sơ thiếu tên thành phần.", item.source
                    )
                )
            if item.is_required_raw and item.is_required is None:
                issues.append(
                    _issue(
                        "error",
                        "DOSSIER_INVALID_REQUIRED",
                        f"Giá trị Bắt buộc không hợp lệ: {item.is_required_raw}",
                        item.source,
                    )
                )
            issues.extend(_validate_urls(item.form_url, item.source, required=False))
        for step in document.procedure_steps:
            if not step.instruction:
                issues.append(
                    _issue(
                        "error",
                        "STEP_MISSING_INSTRUCTION",
                        "Bước thủ tục thiếu hướng dẫn.",
                        step.source,
                    )
                )
            issues.extend(_validate_urls(step.url_or_location, step.source, required=False))
        issues.extend(_validate_procedure(document))
    return issues


def _policy_findings(bundle: ExtractionBundle) -> list[PolicyFinding]:
    missing_basis = sum(1 for faq in bundle.faqs if not faq.legal_basis)
    missing_contact = sum(
        1
        for faq in bundle.faqs
        if not faq.support_contact and not faq.contact_information and not faq.online_channel
    )
    unknown_fees = [
        document.document_code
        for document in bundle.documents
        if document.procedure is not None and document.procedure.fee_type == "unknown"
    ]
    module_ok = bundle.module.name == bundle.module_name
    return [
        PolicyFinding(
            id="DATA-01",
            severity="info" if module_ok else "error",
            message=f"Tên mô-đun theo release: {bundle.module_name}.",
        ),
        PolicyFinding(
            id="DATA-02",
            severity="info",
            message=f"Tên phòng ban theo release: {bundle.department_name}.",
        ),
        PolicyFinding(
            id="DATA-03",
            severity="info",
            message="Routing rule dùng content-based source key vì nguồn chưa có mã ổn định.",
        ),
        PolicyFinding(
            id="DATA-04",
            severity="info",
            message="FAQ không có trạng thái/hiệu lực tại dòng; kế thừa từ release manifest.",
        ),
        PolicyFinding(
            id="DATA-05",
            severity="warning",
            message="FAQ chưa có văn bản căn cứ; warning trong development, review trước UAT.",
            count=missing_basis,
        ),
        PolicyFinding(
            id="DATA-06",
            severity="info",
            message="FAQ không có contact riêng; kế thừa contact module/department đã xác nhận.",
            count=missing_contact,
        ),
        PolicyFinding(
            id="DATA-07",
            severity="warning",
            message="Lệ phí chưa xác định; fee_type=unknown, cấm nêu số tiền.",
            count=len(unknown_fees),
        ),
        PolicyFinding(
            id="DATA-08",
            severity="info",
            message="Workbook được nhận diện bằng schema fingerprint, không chỉ bằng tên file.",
        ),
        PolicyFinding(
            id="DATA-09",
            severity="warning",
            message="Email, hotline và URL chưa được business-verify; chỉ dùng development.",
        ),
        PolicyFinding(
            id="DATA-10",
            severity="info",
            message="Workbook thiếu row-level approval; release manifest là approval envelope.",
        ),
    ]


def validate_bundle(
    bundle: ExtractionBundle,
    manifest: ReleaseManifest,
    *,
    dry_run: bool,
    blocked: bool = False,
    blocked_reason: str | None = None,
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    issues.extend(_validate_routing(bundle))
    issues.extend(_validate_faqs(bundle))
    issues.extend(_validate_documents(bundle))

    if bundle.module.name != manifest.module_name:
        issues.append(
            _issue(
                "error",
                "MODULE_NAME_MISMATCH",
                f"Tên mô-đun không khớp manifest: {bundle.module.name}",
                bundle.module.source,
            )
        )
    if bundle.department_id != manifest.department_id or bundle.module_code != manifest.module_code:
        issues.append(
            _issue(
                "error",
                "CONTEXT_MISMATCH",
                "Department/module trong dữ liệu không khớp release manifest.",
            )
        )

    counts = count_bundle(bundle)
    expected = CountSummary.model_validate(manifest.expected_counts.model_dump())
    if counts != expected:
        issues.append(
            _issue(
                "error",
                "COUNT_MISMATCH",
                "Số lượng record không khớp manifest: "
                f"actual={counts.model_dump()} expected={expected.model_dump()}.",
            )
        )

    if missing_contact := sum(
        1
        for faq in bundle.faqs
        if not faq.support_contact and not faq.contact_information and not faq.online_channel
    ):
        issues.append(
            _issue(
                "info",
                "DATA-06",
                f"{missing_contact} FAQ không có contact riêng; sẽ kế thừa từ module/department.",
            )
        )

    findings = _policy_findings(bundle)
    error_count = sum(1 for item in issues if item.severity == "error")
    warning_count = sum(1 for item in issues if item.severity == "warning")
    info_count = sum(1 for item in issues if item.severity == "info")
    return ValidationReport(
        release_id=bundle.release_id,
        department_id=bundle.department_id,
        module_code=bundle.module_code,
        dry_run=dry_run,
        publish_allowed=not blocked and error_count == 0,
        blocked=blocked,
        blocked_reason=blocked_reason,
        counts=counts,
        expected_counts=expected,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        issues=issues,
        policy_findings=findings,
    )
