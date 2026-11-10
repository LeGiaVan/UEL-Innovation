from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.ingestion.enums import Severity, WorkbookRole


class SourceLocation(BaseModel):
    source_file: str
    source_sheet: str
    source_row: int
    source_column: str | None = None
    source_cell_range: str | None = None


class IdentifiedWorkbook(BaseModel):
    path: str
    name: str
    role: WorkbookRole
    file_sha256: str
    schema_sha256: str
    expected_file_sha256: str
    expected_schema_sha256: str
    checksum_ok: bool
    schema_ok: bool


class RawModule(BaseModel):
    name: str | None
    source_created_at: date | None
    source_updated_at: date | None
    source: SourceLocation
    content_hash: str


class RawRoutingRule(BaseModel):
    source_order: int | None
    source_key: str
    scope_type_raw: str | None
    scope_type: str | None
    topic: str | None
    bot_behavior: str | None
    support_contact: str | None
    contact_information: str | None
    online_channel: str | None
    source: SourceLocation
    content_hash: str


class RawFaq(BaseModel):
    source_order: int | None
    question_code: str | None
    category: str | None
    subcategory: str | None
    question: str | None
    normalized_question: str | None
    answer: str | None
    legal_basis: str | None
    support_contact: str | None
    contact_information: str | None
    online_channel: str | None
    source: SourceLocation
    content_hash: str


class RawRegulationSection(BaseModel):
    source_order: int | None
    heading: str | None
    subheading: str | None
    content: str | None
    condition: str | None
    resolution: str | None
    source: SourceLocation


class RawConditionSection(BaseModel):
    source_order: int | None
    scenario: str | None
    resolution: str | None
    condition_type_raw: str | None
    condition_type: str | None
    source: SourceLocation


class RawProcedure(BaseModel):
    result: str | None
    processing_time_raw: str | None
    processing_time_type: str | None
    max_working_days: int | None
    place: str | None
    submission_url: str | None
    special_schedule: str | None
    fee_type_raw: str | None
    fee_type: str | None
    fee_amount_vnd: int | None
    fee_note: str | None
    answer_policy: str | None
    source: SourceLocation


class RawDossierItem(BaseModel):
    source_order: int | None
    name: str | None
    form_url: str | None
    quantity_specification: str | None
    is_required_raw: str | None
    is_required: bool | None
    source: SourceLocation


class RawProcedureStep(BaseModel):
    step_number: int | None
    instruction: str | None
    url_or_location: str | None
    responsible_unit: str | None
    time_requirement: str | None
    channel: str | None
    source: SourceLocation


class RawDocument(BaseModel):
    document_code: str | None
    title: str | None
    summary: str | None
    aliases: list[str] = Field(default_factory=list)
    document_type: str | None
    regulation_sections: list[RawRegulationSection] = Field(default_factory=list)
    condition_sections: list[RawConditionSection] = Field(default_factory=list)
    procedure: RawProcedure | None = None
    dossier_items: list[RawDossierItem] = Field(default_factory=list)
    procedure_steps: list[RawProcedureStep] = Field(default_factory=list)
    source: SourceLocation
    content_hash: str


class ExtractionBundle(BaseModel):
    department_id: str
    department_name: str
    module_code: str
    module_name: str
    release_id: str
    release_status: str
    source_type: str
    workbooks: list[IdentifiedWorkbook]
    module: RawModule
    routing_rules: list[RawRoutingRule]
    faqs: list[RawFaq]
    documents: list[RawDocument]


class ValidationIssue(BaseModel):
    severity: Severity
    code: str
    message: str
    source_file: str | None = None
    source_sheet: str | None = None
    source_row: int | None = None
    source_column: str | None = None
    record_key: str | None = None


class PolicyFinding(BaseModel):
    id: str
    severity: Severity
    message: str
    count: int | None = None


class CountSummary(BaseModel):
    routing_rules: int
    faqs: int
    documents: int
    regulation_sections: int
    condition_exception_sections: int
    dossier_items: int
    procedure_steps: int


class SilverSummary(BaseModel):
    sync_run_id: str
    status: str
    inserted_count: int = 0
    updated_count: int = 0
    deactivated_count: int = 0
    unchanged_count: int = 0


class GoldSummary(BaseModel):
    status: str
    collection: str = ""
    model: str = ""
    chunk_count: int = 0
    upserted_count: int = 0
    unchanged_count: int = 0
    deleted_count: int = 0
    error_message: str | None = None


class ValidationReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    release_id: str
    department_id: str
    module_code: str
    dry_run: bool
    publish_allowed: bool
    blocked: bool
    blocked_reason: str | None = None
    counts: CountSummary
    expected_counts: CountSummary | None = None
    error_count: int
    warning_count: int
    info_count: int
    issues: list[ValidationIssue]
    policy_findings: list[PolicyFinding]
    bronze_object_keys: list[str] = Field(default_factory=list)
    silver: SilverSummary | None = None
    gold: GoldSummary | None = None


class SyncOutcome(BaseModel):
    status: Literal[
        "validated", "blocked", "validation_failed", "completed", "failed", "partial_failed"
    ]
    report: ValidationReport
    report_json_path: str | None = None
    report_markdown_path: str | None = None
