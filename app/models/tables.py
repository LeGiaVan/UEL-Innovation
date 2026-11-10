from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    audience: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    support_contact: Mapped[str | None] = mapped_column(String(255))
    contact_information: Mapped[str | None] = mapped_column(String(255))
    online_channel: Mapped[str | None] = mapped_column(String(512))
    contact_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    modules: Mapped[list[Module]] = relationship(back_populates="department")


class Module(Base):
    __tablename__ = "modules"
    __table_args__ = (UniqueConstraint("department_id", "code", name="uq_modules_department_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    department_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("departments.id"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_created_at: Mapped[date | None] = mapped_column(Date)
    source_updated_at: Mapped[date | None] = mapped_column(Date)
    release_status: Mapped[str] = mapped_column(String(32), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    support_contact: Mapped[str | None] = mapped_column(String(255))
    contact_information: Mapped[str | None] = mapped_column(String(255))
    online_channel: Mapped[str | None] = mapped_column(String(512))
    contact_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_schema_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(128), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_cell_range: Mapped[str | None] = mapped_column(String(64))
    release_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    last_seen_sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    department: Mapped[Department] = relationship(back_populates="modules")
    routing_rules: Mapped[list[RoutingRule]] = relationship(back_populates="module")
    faqs: Mapped[list[Faq]] = relationship(back_populates="module")
    documents: Mapped[list[Document]] = relationship(back_populates="module")


class RoutingRule(Base):
    __tablename__ = "routing_rules"
    __table_args__ = (
        UniqueConstraint("module_id", "source_key", name="uq_routing_module_source_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    department_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("departments.id"), nullable=False
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("modules.id"), nullable=False
    )
    source_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_order: Mapped[int | None] = mapped_column(Integer)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    bot_behavior: Mapped[str | None] = mapped_column(Text)
    support_contact: Mapped[str | None] = mapped_column(String(255))
    contact_information: Mapped[str | None] = mapped_column(String(255))
    online_channel: Mapped[str | None] = mapped_column(String(512))
    contact_source: Mapped[str] = mapped_column(String(32), nullable=False, default="record")
    contact_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    release_status: Mapped[str] = mapped_column(String(32), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_schema_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(128), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_cell_range: Mapped[str | None] = mapped_column(String(64))
    release_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    last_seen_sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    module: Mapped[Module] = relationship(back_populates="routing_rules")


class Faq(Base):
    __tablename__ = "faqs"
    __table_args__ = (
        UniqueConstraint("module_id", "question_code", name="uq_faqs_module_question_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    department_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("departments.id"), nullable=False
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("modules.id"), nullable=False
    )
    question_code: Mapped[str] = mapped_column(String(64), nullable=False)
    source_order: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str | None] = mapped_column(String(255))
    subcategory: Mapped[str | None] = mapped_column(String(255))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    legal_basis: Mapped[str | None] = mapped_column(Text)
    support_contact: Mapped[str | None] = mapped_column(String(255))
    contact_information: Mapped[str | None] = mapped_column(String(255))
    online_channel: Mapped[str | None] = mapped_column(String(512))
    contact_source: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    contact_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    release_status: Mapped[str] = mapped_column(String(32), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_schema_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(128), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_cell_range: Mapped[str | None] = mapped_column(String(64))
    release_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    last_seen_sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    module: Mapped[Module] = relationship(back_populates="faqs")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("module_id", "document_code", name="uq_documents_module_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    department_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("departments.id"), nullable=False
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("modules.id"), nullable=False
    )
    document_code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    release_status: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_schema_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(128), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_cell_range: Mapped[str | None] = mapped_column(String(64))
    release_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    last_seen_sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    module: Mapped[Module] = relationship(back_populates="documents")
    sections: Mapped[list[DocumentSection]] = relationship(back_populates="document")
    procedure: Mapped[Procedure | None] = relationship(back_populates="document")
    dossier_items: Mapped[list[DossierItem]] = relationship(back_populates="document")
    procedure_steps: Mapped[list[ProcedureStep]] = relationship(back_populates="document")
    attachments: Mapped[list[Attachment]] = relationship(back_populates="document")


class DocumentSection(Base):
    __tablename__ = "document_sections"
    __table_args__ = (
        UniqueConstraint("document_id", "section_key", name="uq_document_sections_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    section_key: Mapped[str] = mapped_column(String(64), nullable=False)
    section_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_order: Mapped[int | None] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(Text)
    subheading: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    condition: Mapped[str | None] = mapped_column(Text)
    scenario: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text)
    condition_type: Mapped[str | None] = mapped_column(String(32))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_schema_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(128), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_cell_range: Mapped[str | None] = mapped_column(String(64))
    release_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    last_seen_sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    document: Mapped[Document] = relationship(back_populates="sections")


class Procedure(Base):
    __tablename__ = "procedures"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id"), unique=True, nullable=False
    )
    result: Mapped[str | None] = mapped_column(Text)
    processing_time_type: Mapped[str | None] = mapped_column(String(32))
    max_working_days: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(Text)
    submission_url: Mapped[str | None] = mapped_column(Text)
    special_schedule: Mapped[str | None] = mapped_column(Text)
    fee_type: Mapped[str | None] = mapped_column(String(32))
    fee_amount_vnd: Mapped[int | None] = mapped_column(Integer)
    fee_note: Mapped[str | None] = mapped_column(Text)
    answer_policy: Mapped[str | None] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_schema_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(128), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_cell_range: Mapped[str | None] = mapped_column(String(64))
    release_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    last_seen_sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    document: Mapped[Document] = relationship(back_populates="procedure")


class DossierItem(Base):
    __tablename__ = "dossier_items"
    __table_args__ = (
        UniqueConstraint("document_id", "source_order", name="uq_dossier_document_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    source_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    form_url: Mapped[str | None] = mapped_column(Text)
    quantity_specification: Mapped[str | None] = mapped_column(Text)
    is_required: Mapped[bool | None] = mapped_column(Boolean)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_schema_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(128), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_cell_range: Mapped[str | None] = mapped_column(String(64))
    release_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    last_seen_sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    document: Mapped[Document] = relationship(back_populates="dossier_items")


class ProcedureStep(Base):
    __tablename__ = "procedure_steps"
    __table_args__ = (
        UniqueConstraint("document_id", "step_number", name="uq_procedure_steps_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    url_or_location: Mapped[str | None] = mapped_column(Text)
    responsible_unit: Mapped[str | None] = mapped_column(String(255))
    time_requirement: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str | None] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_schema_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sheet: Mapped[str] = mapped_column(String(128), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    source_cell_range: Mapped[str | None] = mapped_column(String(64))
    release_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    last_seen_sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    document: Mapped[Document] = relationship(back_populates="procedure_steps")


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        UniqueConstraint("document_id", "source_url", name="uq_attachments_document_url"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id")
    )
    form_code: Mapped[str | None] = mapped_column(String(64))
    file_name: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    object_key: Mapped[str | None] = mapped_column(String(512))
    mime_type: Mapped[str | None] = mapped_column(String(128))
    checksum: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    last_seen_sync_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document: Mapped[Document | None] = relationship(back_populates="attachments")


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    department_code: Mapped[str] = mapped_column(String(64), nullable=False)
    module_code: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    release_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_checksum: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deactivated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    report_object_key: Mapped[str | None] = mapped_column(String(512))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source_records: Mapped[list[SourceRecord]] = relationship(back_populates="sync_run")


class SourceRecord(Base):
    __tablename__ = "source_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=_uuid)
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sync_runs.id"), nullable=False
    )
    workbook: Mapped[str] = mapped_column(String(255), nullable=False)
    sheet: Mapped[str] = mapped_column(String(128), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_key: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    validation_errors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    sync_run: Mapped[SyncRun] = relationship(back_populates="source_records")
