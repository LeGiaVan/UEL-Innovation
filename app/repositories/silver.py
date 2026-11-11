from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import Engine, Select, create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.ingestion.contact import ContactConfig, ResolvedContact, resolve_contact
from app.ingestion.keys import section_key
from app.ingestion.manifest import DepartmentConfig, DepartmentModuleConfig, ReleaseManifest
from app.ingestion.models import ExtractionBundle, IdentifiedWorkbook, SourceLocation
from app.ingestion.normalize import content_hash
from app.models.tables import (
    Attachment,
    Department,
    Document,
    DocumentSection,
    DossierItem,
    Faq,
    Module,
    Procedure,
    ProcedureStep,
    RoutingRule,
    SourceRecord,
    SyncRun,
)

STALE_STATUSES = frozenset({"started", "validating", "loading_silver"})


@dataclass
class SilverStats:
    sync_run_id: uuid.UUID
    status: str = "completed"
    inserted_count: int = 0
    updated_count: int = 0
    deactivated_count: int = 0
    unchanged_count: int = 0

    def record(self, action: str) -> None:
        if action == "inserted":
            self.inserted_count += 1
        elif action == "updated":
            self.updated_count += 1
        elif action == "deactivated":
            self.deactivated_count += 1
        elif action == "unchanged":
            self.unchanged_count += 1


class SilverWriter(Protocol):
    def persist(
        self,
        bundle: ExtractionBundle,
        manifest: ReleaseManifest,
        department: DepartmentConfig,
        module_config: DepartmentModuleConfig,
        environment: str,
    ) -> SilverStats:
        raise NotImplementedError


class NullSilverWriter:
    def persist(
        self,
        bundle: ExtractionBundle,
        manifest: ReleaseManifest,
        department: DepartmentConfig,
        module_config: DepartmentModuleConfig,
        environment: str,
    ) -> SilverStats:
        del bundle, manifest, department, module_config, environment
        return SilverStats(sync_run_id=uuid.uuid4(), status="skipped")


def create_sync_engine(settings: Settings) -> Engine:
    return create_engine(settings.postgres_sync_url, pool_pre_ping=True)


class PostgresSilverWriter:
    def __init__(self, engine: Engine) -> None:
        self._session_factory = sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> PostgresSilverWriter:
        return cls(create_sync_engine(settings or Settings()))

    def persist(
        self,
        bundle: ExtractionBundle,
        manifest: ReleaseManifest,
        department: DepartmentConfig,
        module_config: DepartmentModuleConfig,
        environment: str,
    ) -> SilverStats:
        run_id = uuid.uuid4()
        started = datetime.now(UTC)
        checksums = {
            item.name: {"file_sha256": item.file_sha256, "schema_sha256": item.schema_sha256}
            for item in bundle.workbooks
        }
        with self._session_factory() as session:
            _fail_stale_runs(session, bundle.department_id, bundle.module_code, started)
            session.add(
                SyncRun(
                    id=run_id,
                    department_code=bundle.department_id,
                    module_code=bundle.module_code,
                    source_type=bundle.source_type,
                    release_id=bundle.release_id,
                    status="started",
                    dry_run=False,
                    source_checksum=checksums,
                    started_at=started,
                )
            )
            session.commit()
        stats = SilverStats(sync_run_id=run_id)
        try:
            with self._session_factory() as session:
                run = session.get(SyncRun, run_id)
                if run is None:
                    raise RuntimeError("sync_run disappeared before silver load")
                run.status = "loading_silver"
                self._apply(
                    session,
                    run,
                    bundle,
                    manifest,
                    department,
                    module_config,
                    environment,
                    stats,
                )
                run.status = "completed"
                run.inserted_count = stats.inserted_count
                run.updated_count = stats.updated_count
                run.deactivated_count = stats.deactivated_count
                run.unchanged_count = stats.unchanged_count
                run.completed_at = datetime.now(UTC)
                session.commit()
            stats.status = "completed"
            return stats
        except Exception as exc:
            with self._session_factory() as session:
                run = session.get(SyncRun, run_id)
                if run is not None:
                    run.status = "failed"
                    run.error_message = str(exc)[:2000]
                    run.completed_at = datetime.now(UTC)
                    session.commit()
            stats.status = "failed"
            raise

    def mark_status(self, run_id: uuid.UUID, status: str, error_message: str | None = None) -> None:
        now = datetime.now(UTC)
        with self._session_factory() as session:
            run = session.get(SyncRun, run_id)
            if run is None:
                return
            run.status = status
            if error_message:
                run.error_message = error_message[:2000]
            run.completed_at = now
            session.commit()

    def _apply(
        self,
        session: Session,
        run: SyncRun,
        bundle: ExtractionBundle,
        manifest: ReleaseManifest,
        department_config: DepartmentConfig,
        module_config: DepartmentModuleConfig,
        environment: str,
        stats: SilverStats,
    ) -> None:
        now = datetime.now(UTC)
        allow_unverified = environment in {"development", "test"}
        department = _upsert_department(session, department_config, now, stats)
        module = _upsert_module(
            session,
            department,
            bundle,
            manifest,
            module_config,
            run.id,
            now,
            stats,
        )
        files = {item.name: item for item in bundle.workbooks}
        for rule in bundle.routing_rules:
            if not rule.scope_type or not rule.topic:
                continue
            action = _upsert_routing_rule(
                session,
                department,
                module,
                bundle,
                rule,
                files,
                run.id,
                now,
                allow_unverified,
                department_config.contact,
                module_config.contact,
                stats,
            )
            _add_source_record(
                session, run.id, "routing_rule", rule.source_key, rule.source, rule, action
            )
        for faq in bundle.faqs:
            if not faq.question_code or not faq.question or not faq.answer:
                continue
            action = _upsert_faq(
                session,
                department,
                module,
                bundle,
                faq,
                files,
                run.id,
                now,
                allow_unverified,
                department_config.contact,
                module_config.contact,
                stats,
            )
            _add_source_record(session, run.id, "faq", faq.question_code, faq.source, faq, action)
        for document in bundle.documents:
            if not document.document_code or not document.title or not document.document_type:
                continue
            _upsert_document_tree(
                session,
                department,
                module,
                bundle,
                document,
                files,
                run.id,
                now,
                stats,
            )
        stats.deactivated_count += _deactivate_missing(session, RoutingRule, module.id, run.id, now)
        stats.deactivated_count += _deactivate_missing(session, Faq, module.id, run.id, now)
        stats.deactivated_count += _deactivate_missing(session, Document, module.id, run.id, now)
        document_ids: Select[Any] = select(Document.id).where(Document.module_id == module.id)
        for model in (DocumentSection, Procedure, DossierItem, ProcedureStep, Attachment):
            stats.deactivated_count += _deactivate_missing_children(
                session, model, document_ids, run.id, now
            )


def _fail_stale_runs(
    session: Session, department_code: str, module_code: str, now: datetime
) -> None:
    session.execute(
        update(SyncRun)
        .where(
            SyncRun.department_code == department_code,
            SyncRun.module_code == module_code,
            SyncRun.status.in_(STALE_STATUSES),
        )
        .values(status="failed", error_message="stale sync run superseded", completed_at=now)
    )


def _file(files: dict[str, IdentifiedWorkbook], name: str) -> IdentifiedWorkbook:
    return files[name]


def _source_fields(location: SourceLocation, workbook: IdentifiedWorkbook) -> dict[str, Any]:
    return {
        "source_file": location.source_file,
        "source_file_sha256": workbook.file_sha256,
        "source_schema_sha256": workbook.schema_sha256,
        "source_sheet": location.source_sheet,
        "source_row": location.source_row,
        "source_cell_range": location.source_cell_range,
    }


def _add_source_record(
    session: Session,
    run_id: uuid.UUID,
    entity_type: str,
    source_key: str,
    location: SourceLocation,
    payload: Any,
    action: str,
) -> None:
    session.add(
        SourceRecord(
            sync_run_id=run_id,
            workbook=location.source_file,
            sheet=location.source_sheet,
            row_number=location.source_row,
            source_key=source_key,
            entity_type=entity_type,
            raw_payload=payload.model_dump(mode="json"),
            validation_status=action,
            validation_errors=[],
        )
    )


def _upsert_department(
    session: Session,
    config: DepartmentConfig,
    now: datetime,
    stats: SilverStats,
) -> Department:
    row = session.scalar(select(Department).where(Department.code == config.id))
    name = config.name
    if row is None:
        row = Department(
            code=config.id,
            name=name,
            audience=config.audience,
            is_active=True,
            support_contact=config.contact.support_contact or name,
            contact_information=config.contact.contact_information,
            online_channel=config.contact.online_channel,
            contact_verified=config.contact.verified,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.flush()
        stats.record("inserted")
        return row
    changed = (
        row.name != name
        or row.audience != config.audience
        or row.support_contact != (config.contact.support_contact or name)
        or row.contact_information != config.contact.contact_information
        or row.online_channel != config.contact.online_channel
        or row.contact_verified != config.contact.verified
        or row.is_active is False
    )
    row.name = name
    row.audience = config.audience
    row.is_active = True
    row.support_contact = config.contact.support_contact or name
    row.contact_information = config.contact.contact_information
    row.online_channel = config.contact.online_channel
    row.contact_verified = config.contact.verified
    if changed:
        row.updated_at = now
        stats.record("updated")
    else:
        stats.record("unchanged")
    return row


def _upsert_module(
    session: Session,
    department: Department,
    bundle: ExtractionBundle,
    manifest: ReleaseManifest,
    module_config: DepartmentModuleConfig,
    run_id: uuid.UUID,
    now: datetime,
    stats: SilverStats,
) -> Module:
    name = bundle.module.name or module_config.name
    workbook = next(item for item in bundle.workbooks if item.role == "module_and_routing")
    content = content_hash(name, manifest.release_status)
    row = session.scalar(
        select(Module).where(
            Module.department_id == department.id, Module.code == bundle.module_code
        )
    )
    values = {
        "name": name,
        "source_created_at": bundle.module.source_created_at,
        "source_updated_at": bundle.module.source_updated_at,
        "release_status": manifest.release_status,
        "content_hash": content,
        "is_active": True,
        "support_contact": module_config.contact.support_contact or department.support_contact,
        "contact_information": (
            module_config.contact.contact_information or department.contact_information
        ),
        "online_channel": module_config.contact.online_channel or department.online_channel,
        "contact_verified": module_config.contact.verified or department.contact_verified,
        **_source_fields(bundle.module.source, workbook),
        "release_id": manifest.release_id,
        "sync_run_id": run_id,
        "last_seen_sync_run_id": run_id,
        "ingested_at": now,
        "updated_at": now,
    }
    if row is None:
        row = Module(department_id=department.id, code=bundle.module_code, created_at=now, **values)
        session.add(row)
        session.flush()
        stats.record("inserted")
        return row
    unchanged = row.content_hash == content and row.is_active
    for key, value in values.items():
        setattr(row, key, value)
    stats.record("unchanged" if unchanged else "updated")
    return row


def _resolved(
    record_support: str | None,
    record_information: str | None,
    record_channel: str | None,
    module_contact: ContactConfig,
    department_contact: ContactConfig,
    allow_unverified: bool,
) -> ResolvedContact:
    return resolve_contact(
        record_support=record_support,
        record_information=record_information,
        record_channel=record_channel,
        module=module_contact,
        department=department_contact,
        allow_unverified_inheritance=allow_unverified,
    )


def _upsert_routing_rule(
    session: Session,
    department: Department,
    module: Module,
    bundle: ExtractionBundle,
    rule: Any,
    files: dict[str, IdentifiedWorkbook],
    run_id: uuid.UUID,
    now: datetime,
    allow_unverified: bool,
    department_contact: ContactConfig,
    module_contact: ContactConfig,
    stats: SilverStats,
) -> str:
    workbook = _file(files, rule.source.source_file)
    contact = _resolved(
        rule.support_contact,
        rule.contact_information,
        rule.online_channel,
        module_contact,
        department_contact,
        allow_unverified,
    )
    row = session.scalar(
        select(RoutingRule).where(
            RoutingRule.module_id == module.id, RoutingRule.source_key == rule.source_key
        )
    )
    values = {
        "department_id": department.id,
        "source_order": rule.source_order,
        "scope_type": rule.scope_type,
        "topic": rule.topic,
        "bot_behavior": rule.bot_behavior,
        "support_contact": contact.support_contact,
        "contact_information": contact.contact_information,
        "online_channel": contact.online_channel,
        "contact_source": contact.source,
        "contact_verified": contact.verified,
        "release_status": bundle.release_status,
        "content_hash": rule.content_hash,
        "is_active": True,
        "deactivated_at": None,
        **_source_fields(rule.source, workbook),
        "release_id": bundle.release_id,
        "sync_run_id": run_id,
        "last_seen_sync_run_id": run_id,
        "ingested_at": now,
        "updated_at": now,
    }
    return _upsert_row(
        session,
        row,
        RoutingRule,
        {"module_id": module.id, "source_key": rule.source_key, "created_at": now, **values},
        values,
        rule.content_hash,
        stats,
        now,
    )


def _upsert_faq(
    session: Session,
    department: Department,
    module: Module,
    bundle: ExtractionBundle,
    faq: Any,
    files: dict[str, IdentifiedWorkbook],
    run_id: uuid.UUID,
    now: datetime,
    allow_unverified: bool,
    department_contact: ContactConfig,
    module_contact: ContactConfig,
    stats: SilverStats,
) -> str:
    workbook = _file(files, faq.source.source_file)
    contact = _resolved(
        faq.support_contact,
        faq.contact_information,
        faq.online_channel,
        module_contact,
        department_contact,
        allow_unverified,
    )
    row = session.scalar(
        select(Faq).where(Faq.module_id == module.id, Faq.question_code == faq.question_code)
    )
    values = {
        "department_id": department.id,
        "source_order": faq.source_order,
        "category": faq.category,
        "subcategory": faq.subcategory,
        "question": faq.question,
        "normalized_question": faq.normalized_question or faq.question,
        "answer": faq.answer,
        "legal_basis": faq.legal_basis,
        "support_contact": contact.support_contact,
        "contact_information": contact.contact_information,
        "online_channel": contact.online_channel,
        "contact_source": contact.source,
        "contact_verified": contact.verified,
        "release_status": bundle.release_status,
        "content_hash": faq.content_hash,
        "is_active": True,
        "deactivated_at": None,
        **_source_fields(faq.source, workbook),
        "release_id": bundle.release_id,
        "sync_run_id": run_id,
        "last_seen_sync_run_id": run_id,
        "ingested_at": now,
        "updated_at": now,
    }
    return _upsert_row(
        session,
        row,
        Faq,
        {
            "module_id": module.id,
            "question_code": faq.question_code,
            "created_at": now,
            **values,
        },
        values,
        faq.content_hash,
        stats,
        now,
    )


def _upsert_document_tree(
    session: Session,
    department: Department,
    module: Module,
    bundle: ExtractionBundle,
    document: Any,
    files: dict[str, IdentifiedWorkbook],
    run_id: uuid.UUID,
    now: datetime,
    stats: SilverStats,
) -> None:
    workbook = _file(files, document.source.source_file)
    row = session.scalar(
        select(Document).where(
            Document.module_id == module.id, Document.document_code == document.document_code
        )
    )
    values = {
        "department_id": department.id,
        "title": document.title,
        "summary": document.summary,
        "aliases": document.aliases,
        "document_type": document.document_type,
        "release_status": bundle.release_status,
        "effective_from": None,
        "effective_to": None,
        "content_hash": document.content_hash,
        "is_active": True,
        "deactivated_at": None,
        **_source_fields(document.source, workbook),
        "release_id": bundle.release_id,
        "sync_run_id": run_id,
        "last_seen_sync_run_id": run_id,
        "ingested_at": now,
        "updated_at": now,
    }
    _upsert_row(
        session,
        row,
        Document,
        {
            "module_id": module.id,
            "document_code": document.document_code,
            "created_at": now,
            **values,
        },
        values,
        document.content_hash,
        stats,
        now,
    )
    persisted = session.scalar(
        select(Document).where(
            Document.module_id == module.id, Document.document_code == document.document_code
        )
    )
    assert persisted is not None
    _add_source_record(
        session, run_id, "document", document.document_code, document.source, document, "upserted"
    )
    for section in document.regulation_sections:
        heading = section.heading
        key = section_key(document.document_code, "regulation", heading, section.source_order)
        hash_value = content_hash(heading, section.subheading, section.content, section.resolution)
        existing = session.scalar(
            select(DocumentSection).where(
                DocumentSection.document_id == persisted.id, DocumentSection.section_key == key
            )
        )
        section_values = {
            "section_type": "regulation",
            "source_order": section.source_order,
            "heading": heading,
            "subheading": section.subheading,
            "content": section.content,
            "condition": section.condition,
            "scenario": None,
            "resolution": section.resolution,
            "condition_type": None,
            "content_hash": hash_value,
            "is_active": True,
            "deactivated_at": None,
            **_source_fields(section.source, workbook),
            "release_id": bundle.release_id,
            "sync_run_id": run_id,
            "last_seen_sync_run_id": run_id,
            "ingested_at": now,
            "updated_at": now,
        }
        _upsert_row(
            session,
            existing,
            DocumentSection,
            {"document_id": persisted.id, "section_key": key, "created_at": now, **section_values},
            section_values,
            hash_value,
            stats,
            now,
        )
    for section in document.condition_sections:
        section_type = section.condition_type or "note"
        key = section_key(
            document.document_code, section_type, section.scenario, section.source_order
        )
        hash_value = content_hash(section.scenario, section.resolution, section_type)
        existing = session.scalar(
            select(DocumentSection).where(
                DocumentSection.document_id == persisted.id, DocumentSection.section_key == key
            )
        )
        section_values = {
            "section_type": section_type,
            "source_order": section.source_order,
            "heading": None,
            "subheading": None,
            "content": None,
            "condition": None,
            "scenario": section.scenario,
            "resolution": section.resolution,
            "condition_type": section_type,
            "content_hash": hash_value,
            "is_active": True,
            "deactivated_at": None,
            **_source_fields(section.source, workbook),
            "release_id": bundle.release_id,
            "sync_run_id": run_id,
            "last_seen_sync_run_id": run_id,
            "ingested_at": now,
            "updated_at": now,
        }
        _upsert_row(
            session,
            existing,
            DocumentSection,
            {"document_id": persisted.id, "section_key": key, "created_at": now, **section_values},
            section_values,
            hash_value,
            stats,
            now,
        )
    if document.procedure is not None:
        procedure = document.procedure
        hash_value = content_hash(
            procedure.result,
            procedure.processing_time_type,
            str(procedure.max_working_days) if procedure.max_working_days else None,
            procedure.fee_type,
            procedure.fee_note,
        )
        existing_proc = session.scalar(
            select(Procedure).where(Procedure.document_id == persisted.id)
        )
        proc_values = {
            "result": procedure.result,
            "processing_time_type": procedure.processing_time_type,
            "max_working_days": procedure.max_working_days,
            "location": procedure.place,
            "submission_url": procedure.submission_url,
            "special_schedule": procedure.special_schedule,
            "fee_type": procedure.fee_type,
            "fee_amount_vnd": procedure.fee_amount_vnd,
            "fee_note": procedure.fee_note,
            "answer_policy": procedure.answer_policy,
            "content_hash": hash_value,
            "is_active": True,
            "deactivated_at": None,
            **_source_fields(procedure.source, workbook),
            "release_id": bundle.release_id,
            "sync_run_id": run_id,
            "last_seen_sync_run_id": run_id,
            "ingested_at": now,
            "updated_at": now,
        }
        _upsert_row(
            session,
            existing_proc,
            Procedure,
            {"document_id": persisted.id, "created_at": now, **proc_values},
            proc_values,
            hash_value,
            stats,
            now,
        )
    for item in document.dossier_items:
        if not item.name or item.source_order is None:
            continue
        hash_value = content_hash(item.name, item.form_url, item.quantity_specification)
        existing_item = session.scalar(
            select(DossierItem).where(
                DossierItem.document_id == persisted.id,
                DossierItem.source_order == item.source_order,
            )
        )
        item_values = {
            "name": item.name,
            "form_url": item.form_url,
            "quantity_specification": item.quantity_specification,
            "is_required": item.is_required,
            "content_hash": hash_value,
            "is_active": True,
            "deactivated_at": None,
            **_source_fields(item.source, workbook),
            "release_id": bundle.release_id,
            "sync_run_id": run_id,
            "last_seen_sync_run_id": run_id,
            "ingested_at": now,
            "updated_at": now,
        }
        _upsert_row(
            session,
            existing_item,
            DossierItem,
            {
                "document_id": persisted.id,
                "source_order": item.source_order,
                "created_at": now,
                **item_values,
            },
            item_values,
            hash_value,
            stats,
            now,
        )
        if item.form_url:
            existing_att = session.scalar(
                select(Attachment).where(
                    Attachment.document_id == persisted.id,
                    Attachment.source_url == item.form_url,
                )
            )
            att_values = {
                "form_code": None,
                "file_name": None,
                "object_key": None,
                "mime_type": None,
                "checksum": None,
                "status": "pending",
                "is_active": True,
                "deactivated_at": None,
                "sync_run_id": run_id,
                "last_seen_sync_run_id": run_id,
                "updated_at": now,
            }
            if existing_att is None:
                session.add(
                    Attachment(
                        document_id=persisted.id,
                        source_url=item.form_url,
                        created_at=now,
                        **att_values,
                    )
                )
                stats.record("inserted")
            else:
                unchanged = existing_att.is_active and existing_att.source_url == item.form_url
                for key, value in att_values.items():
                    setattr(existing_att, key, value)
                stats.record("unchanged" if unchanged else "updated")
    for step in document.procedure_steps:
        if step.step_number is None or not step.instruction:
            continue
        hash_value = content_hash(step.instruction, step.url_or_location, step.responsible_unit)
        existing_step = session.scalar(
            select(ProcedureStep).where(
                ProcedureStep.document_id == persisted.id,
                ProcedureStep.step_number == step.step_number,
            )
        )
        step_values = {
            "instruction": step.instruction,
            "url_or_location": step.url_or_location,
            "responsible_unit": step.responsible_unit,
            "time_requirement": step.time_requirement,
            "channel": step.channel,
            "content_hash": hash_value,
            "is_active": True,
            "deactivated_at": None,
            **_source_fields(step.source, workbook),
            "release_id": bundle.release_id,
            "sync_run_id": run_id,
            "last_seen_sync_run_id": run_id,
            "ingested_at": now,
            "updated_at": now,
        }
        _upsert_row(
            session,
            existing_step,
            ProcedureStep,
            {
                "document_id": persisted.id,
                "step_number": step.step_number,
                "created_at": now,
                **step_values,
            },
            step_values,
            hash_value,
            stats,
            now,
        )


def _upsert_row(
    session: Session,
    existing: Any,
    model: type[Any],
    insert_values: dict[str, Any],
    update_values: dict[str, Any],
    new_hash: str,
    stats: SilverStats,
    now: datetime,
) -> str:
    if existing is None:
        session.add(model(**insert_values))
        session.flush()
        stats.record("inserted")
        return "inserted"
    unchanged = existing.content_hash == new_hash and existing.is_active
    for key, value in update_values.items():
        setattr(existing, key, value)
    if unchanged:
        existing.updated_at = existing.updated_at or now
        stats.record("unchanged")
        return "unchanged"
    stats.record("updated")
    return "updated"


def _deactivate_missing(
    session: Session,
    model: type[Any],
    module_id: uuid.UUID,
    run_id: uuid.UUID,
    now: datetime,
) -> int:
    result = session.execute(
        update(model)
        .where(
            model.module_id == module_id,
            model.last_seen_sync_run_id != run_id,
            model.is_active.is_(True),
        )
        .values(is_active=False, deactivated_at=now, sync_run_id=run_id, updated_at=now)
    )
    return int(getattr(result, "rowcount", 0) or 0)


def _deactivate_missing_children(
    session: Session,
    model: type[Any],
    document_ids: Select[Any],
    run_id: uuid.UUID,
    now: datetime,
) -> int:
    result = session.execute(
        update(model)
        .where(
            model.document_id.in_(document_ids),
            model.last_seen_sync_run_id != run_id,
            model.is_active.is_(True),
        )
        .values(is_active=False, deactivated_at=now, sync_run_id=run_id, updated_at=now)
    )
    return int(getattr(result, "rowcount", 0) or 0)
