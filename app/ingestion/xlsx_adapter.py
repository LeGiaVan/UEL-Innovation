from __future__ import annotations

import hashlib
import re
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.ingestion.adapter import SourceAdapter
from app.ingestion.enums import (
    CONDITION_TYPE_MAP,
    PROCESSING_TIME_MAP,
    REQUIRED_FLAG_MAP,
    ROUTING_SCOPE_MAP,
    UNKNOWN_FEE_MARKER,
    WorkbookRole,
)
from app.ingestion.exceptions import SchemaDriftError
from app.ingestion.fingerprints import (
    FAQ_DATA_SHEET,
    MODULE_DATA_SHEET,
    identify_workbook,
    is_document_data_sheet,
)
from app.ingestion.manifest import ReleaseManifest
from app.ingestion.models import (
    ExtractionBundle,
    IdentifiedWorkbook,
    RawConditionSection,
    RawDocument,
    RawDossierItem,
    RawFaq,
    RawModule,
    RawProcedure,
    RawProcedureStep,
    RawRegulationSection,
    RawRoutingRule,
    SourceLocation,
)
from app.ingestion.normalize import (
    content_hash,
    normalize_question,
    normalize_space,
    optional_date,
    optional_int,
    optional_text,
)

DOCUMENT_CODE_PATTERN = re.compile(r"(TL\d+)", re.IGNORECASE)


def _location(
    workbook_name: str,
    sheet: str,
    row: int,
    column: int | None = None,
    cell_range: str | None = None,
) -> SourceLocation:
    column_letter = get_column_letter(column) if column else None
    return SourceLocation(
        source_file=workbook_name,
        source_sheet=sheet,
        source_row=row,
        source_column=column_letter,
        source_cell_range=cell_range or (f"{column_letter}{row}" if column_letter else None),
    )


def _routing_source_key(
    department_id: str,
    module_code: str,
    scope_type: str,
    topic: str,
) -> str:
    normalized_topic = normalize_space(topic).lower()
    digest = hashlib.sha256(
        f"{department_id}|{module_code}|{scope_type}|{normalized_topic}".encode()
    ).hexdigest()
    return f"route:{digest[:20]}"


def _split_aliases(value: str | None) -> list[str]:
    if not value:
        return []
    seen: set[str] = set()
    aliases: list[str] = []
    for part in value.split(";"):
        item = normalize_space(part)
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            aliases.append(item)
    return aliases


def parse_module(workbook: Workbook, workbook_name: str) -> RawModule:
    worksheet = workbook[MODULE_DATA_SHEET]
    name = optional_text(worksheet["C4"].value)
    return RawModule(
        name=name,
        source_created_at=optional_date(worksheet["C5"].value),
        source_updated_at=optional_date(worksheet["C6"].value),
        source=_location(workbook_name, MODULE_DATA_SHEET, 4, 3, "C4:C6"),
        content_hash=content_hash(name),
    )


def parse_routing_rules(
    workbook: Workbook,
    workbook_name: str,
    department_id: str,
    module_code: str,
) -> list[RawRoutingRule]:
    worksheet = workbook[MODULE_DATA_SHEET]
    rules: list[RawRoutingRule] = []
    for row in range(10, worksheet.max_row + 1):
        scope_raw = optional_text(worksheet.cell(row, 2).value)
        topic = optional_text(worksheet.cell(row, 3).value, multiline=True)
        if scope_raw is None and topic is None:
            continue
        scope_type = ROUTING_SCOPE_MAP.get(scope_raw) if scope_raw else None
        source_key = _routing_source_key(
            department_id,
            module_code,
            scope_type or scope_raw or "",
            topic or "",
        )
        bot_behavior = optional_text(worksheet.cell(row, 4).value, multiline=True)
        support_contact = optional_text(worksheet.cell(row, 5).value)
        contact_information = optional_text(worksheet.cell(row, 6).value)
        online_channel = optional_text(worksheet.cell(row, 7).value)
        rules.append(
            RawRoutingRule(
                source_order=optional_int(worksheet.cell(row, 1).value),
                source_key=source_key,
                scope_type_raw=scope_raw,
                scope_type=scope_type,
                topic=topic,
                bot_behavior=bot_behavior,
                support_contact=support_contact,
                contact_information=contact_information,
                online_channel=online_channel,
                source=_location(workbook_name, MODULE_DATA_SHEET, row, 2, f"A{row}:G{row}"),
                content_hash=content_hash(
                    scope_type,
                    topic,
                    bot_behavior,
                    support_contact,
                    contact_information,
                    online_channel,
                ),
            )
        )
    return rules


def parse_faqs(workbook: Workbook, workbook_name: str) -> list[RawFaq]:
    worksheet = workbook[FAQ_DATA_SHEET]
    faqs: list[RawFaq] = []
    for row in range(5, worksheet.max_row + 1):
        question_code = optional_text(worksheet.cell(row, 3).value)
        question = optional_text(worksheet.cell(row, 6).value, multiline=True)
        answer = optional_text(worksheet.cell(row, 7).value, multiline=True)
        category = optional_text(worksheet.cell(row, 4).value)
        subcategory = optional_text(worksheet.cell(row, 5).value)
        legal_basis = optional_text(worksheet.cell(row, 8).value, multiline=True)
        support_contact = optional_text(worksheet.cell(row, 9).value)
        contact_information = optional_text(worksheet.cell(row, 10).value)
        online_channel = optional_text(worksheet.cell(row, 11).value)
        if not any(
            (
                question_code,
                question,
                answer,
                category,
                subcategory,
                legal_basis,
                support_contact,
                contact_information,
                online_channel,
            )
        ):
            continue
        faqs.append(
            RawFaq(
                source_order=optional_int(worksheet.cell(row, 2).value),
                question_code=question_code,
                category=category,
                subcategory=subcategory,
                question=question,
                normalized_question=normalize_question(question) if question else None,
                answer=answer,
                legal_basis=legal_basis,
                support_contact=support_contact,
                contact_information=contact_information,
                online_channel=online_channel,
                source=_location(workbook_name, FAQ_DATA_SHEET, row, 3, f"B{row}:K{row}"),
                content_hash=content_hash(question_code, question, answer, legal_basis),
            )
        )
    return faqs


def _parse_regulation_sections(
    worksheet: Worksheet,
    workbook_name: str,
) -> list[RawRegulationSection]:
    sections: list[RawRegulationSection] = []
    for row in range(10, 20):
        heading = optional_text(worksheet.cell(row, 2).value)
        subheading = optional_text(worksheet.cell(row, 3).value)
        content = optional_text(worksheet.cell(row, 4).value, multiline=True)
        condition = optional_text(worksheet.cell(row, 5).value, multiline=True)
        resolution = optional_text(worksheet.cell(row, 6).value, multiline=True)
        if not any((heading, subheading, content, condition, resolution)):
            continue
        sections.append(
            RawRegulationSection(
                source_order=optional_int(worksheet.cell(row, 1).value),
                heading=heading,
                subheading=subheading,
                content=content,
                condition=condition,
                resolution=resolution,
                source=_location(workbook_name, worksheet.title, row, 4, f"A{row}:F{row}"),
            )
        )
    return sections


def _parse_condition_sections(
    worksheet: Worksheet,
    workbook_name: str,
) -> list[RawConditionSection]:
    sections: list[RawConditionSection] = []
    for row in range(23, 33):
        scenario = optional_text(worksheet.cell(row, 2).value, multiline=True)
        resolution = optional_text(worksheet.cell(row, 4).value, multiline=True)
        condition_type_raw = optional_text(worksheet.cell(row, 5).value)
        if scenario is None and resolution is None and condition_type_raw is None:
            continue
        sections.append(
            RawConditionSection(
                source_order=optional_int(worksheet.cell(row, 1).value),
                scenario=scenario,
                resolution=resolution,
                condition_type_raw=condition_type_raw,
                condition_type=CONDITION_TYPE_MAP.get(condition_type_raw)
                if condition_type_raw
                else None,
                source=_location(workbook_name, worksheet.title, row, 2, f"A{row}:E{row}"),
            )
        )
    return sections


def _parse_procedure(worksheet: Worksheet, workbook_name: str) -> RawProcedure | None:
    values = {
        row: optional_text(worksheet.cell(row, 3).value, multiline=True) for row in range(35, 44)
    }
    if not any(values.values()):
        return None
    fee_note = values[43]
    fee_type_raw = values[41]
    if fee_note and UNKNOWN_FEE_MARKER in fee_note.lower():
        fee_type = "unknown"
        answer_policy = "abstain_or_handoff"
        fee_amount = None
    else:
        fee_type = None
        answer_policy = None
        fee_amount = optional_int(values[42])
    processing_raw = values[36]
    processing_type = (
        PROCESSING_TIME_MAP.get(processing_raw) if processing_raw else "not_applicable"
    )
    return RawProcedure(
        result=values[35],
        processing_time_raw=processing_raw,
        processing_time_type=processing_type,
        max_working_days=optional_int(values[37]),
        place=values[38],
        submission_url=values[39],
        special_schedule=values[40],
        fee_type_raw=fee_type_raw,
        fee_type=fee_type or ("not_applicable" if not fee_type_raw else None),
        fee_amount_vnd=fee_amount,
        fee_note=fee_note,
        answer_policy=answer_policy,
        source=_location(workbook_name, worksheet.title, 35, 3, "B35:C43"),
    )


def _parse_dossier_items(worksheet: Worksheet, workbook_name: str) -> list[RawDossierItem]:
    items: list[RawDossierItem] = []
    for row in range(47, 57):
        name = optional_text(worksheet.cell(row, 2).value)
        form_url = optional_text(worksheet.cell(row, 3).value)
        quantity = optional_text(worksheet.cell(row, 4).value)
        required_raw = optional_text(worksheet.cell(row, 5).value)
        if not any((name, form_url, quantity, required_raw)):
            continue
        items.append(
            RawDossierItem(
                source_order=optional_int(worksheet.cell(row, 1).value),
                name=name,
                form_url=form_url,
                quantity_specification=quantity,
                is_required_raw=required_raw,
                is_required=REQUIRED_FLAG_MAP.get(required_raw) if required_raw else None,
                source=_location(workbook_name, worksheet.title, row, 2, f"A{row}:E{row}"),
            )
        )
    return items


def _parse_procedure_steps(worksheet: Worksheet, workbook_name: str) -> list[RawProcedureStep]:
    steps: list[RawProcedureStep] = []
    for row in range(60, 72):
        instruction = optional_text(worksheet.cell(row, 2).value, multiline=True)
        url_or_location = optional_text(worksheet.cell(row, 3).value)
        responsible_unit = optional_text(worksheet.cell(row, 4).value)
        time_requirement = optional_text(worksheet.cell(row, 5).value)
        channel = optional_text(worksheet.cell(row, 6).value)
        if not any((instruction, url_or_location, responsible_unit, time_requirement, channel)):
            continue
        steps.append(
            RawProcedureStep(
                step_number=optional_int(worksheet.cell(row, 1).value),
                instruction=instruction,
                url_or_location=url_or_location,
                responsible_unit=responsible_unit,
                time_requirement=time_requirement,
                channel=channel,
                source=_location(workbook_name, worksheet.title, row, 2, f"A{row}:F{row}"),
            )
        )
    return steps


def _infer_document_type(document: RawDocument) -> str | None:
    has_regulation = bool(document.regulation_sections)
    has_procedure = (
        document.procedure is not None
        or bool(document.procedure_steps)
        or bool(document.dossier_items)
    )
    if has_regulation and has_procedure:
        return "regulation_and_procedure"
    if has_regulation:
        return "regulation"
    if has_procedure:
        return "procedure"
    return None


def parse_document(worksheet: Worksheet, workbook_name: str) -> RawDocument:
    code_raw = optional_text(worksheet["C1"].value)
    match = DOCUMENT_CODE_PATTERN.search(code_raw or "")
    document_code = match.group(1).upper() if match else None
    title = optional_text(worksheet["C4"].value)
    summary = optional_text(worksheet["C5"].value, multiline=True)
    aliases = _split_aliases(optional_text(worksheet["C6"].value))
    document = RawDocument(
        document_code=document_code,
        title=title,
        summary=summary,
        aliases=aliases,
        document_type=None,
        regulation_sections=_parse_regulation_sections(worksheet, workbook_name),
        condition_sections=_parse_condition_sections(worksheet, workbook_name),
        procedure=_parse_procedure(worksheet, workbook_name),
        dossier_items=_parse_dossier_items(worksheet, workbook_name),
        procedure_steps=_parse_procedure_steps(worksheet, workbook_name),
        source=_location(workbook_name, worksheet.title, 1, 3, "C1"),
        content_hash="",
    )
    document.document_type = _infer_document_type(document)
    document.content_hash = content_hash(
        document.document_code,
        document.title,
        document.summary,
        document.document_type,
    )
    return document


def parse_documents(workbook: Workbook, workbook_name: str) -> list[RawDocument]:
    documents: list[RawDocument] = []
    for sheet_name in workbook.sheetnames:
        if not is_document_data_sheet(sheet_name):
            continue
        documents.append(parse_document(workbook[sheet_name], workbook_name))
    return documents


class XlsxSourceAdapter(SourceAdapter):
    source_type = "xlsx"

    def list_workbooks(self, source_path: Path) -> list[Path]:
        return sorted(path for path in source_path.glob("*.xlsx") if not path.name.startswith("~$"))

    def identify(
        self,
        source_path: Path,
        manifest: ReleaseManifest,
    ) -> list[IdentifiedWorkbook]:
        identified: list[IdentifiedWorkbook] = []
        for path in self.list_workbooks(source_path):
            try:
                identified.append(identify_workbook(path, manifest))
            except SchemaDriftError:
                continue
        return identified

    def extract(
        self,
        source_path: Path,
        manifest: ReleaseManifest,
        workbooks: list[IdentifiedWorkbook],
    ) -> ExtractionBundle:
        del source_path
        by_role = {item.role: item for item in workbooks}
        required_roles: tuple[WorkbookRole, ...] = (
            "module_and_routing",
            "faq",
            "business_documents",
        )
        missing = [role for role in required_roles if role not in by_role]
        if missing:
            raise SchemaDriftError(f"Release is missing workbooks for roles: {', '.join(missing)}")

        module_wb = _load(by_role["module_and_routing"])
        faq_wb = _load(by_role["faq"])
        documents_wb = _load(by_role["business_documents"])
        module = parse_module(module_wb, by_role["module_and_routing"].name)
        return ExtractionBundle(
            department_id=manifest.department_id,
            department_name=manifest.department_name,
            module_code=manifest.module_code,
            module_name=manifest.module_name,
            release_id=manifest.release_id,
            release_status=manifest.release_status,
            source_type=manifest.source_type,
            workbooks=workbooks,
            module=module,
            routing_rules=parse_routing_rules(
                module_wb,
                by_role["module_and_routing"].name,
                manifest.department_id,
                manifest.module_code,
            ),
            faqs=parse_faqs(faq_wb, by_role["faq"].name),
            documents=parse_documents(documents_wb, by_role["business_documents"].name),
        )


def _load(workbook: IdentifiedWorkbook) -> Workbook:
    return load_workbook(workbook.path, data_only=True, read_only=False)
