from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.gold.ids import gold_chunk_id, point_uuid
from app.gold.models import GoldChunk, GoldEntityType
from app.gold.policy import is_indexable
from app.gold.stair import (
    headings_related,
    serialize_condition,
    serialize_dossier,
    serialize_faq,
    serialize_procedure,
    serialize_regulation,
    serialize_step,
)
from app.ingestion.normalize import content_hash, redact_contact_text
from app.models.tables import Department, Document, DocumentSection, Module


def build_gold_chunks(
    session: Session,
    *,
    department_id: str,
    module_code: str,
    environment: str,
) -> list[GoldChunk]:
    module = session.scalar(
        select(Module)
        .options(
            selectinload(Module.department),
            selectinload(Module.faqs),
            selectinload(Module.documents).selectinload(Document.sections),
            selectinload(Module.documents).selectinload(Document.procedure),
            selectinload(Module.documents).selectinload(Document.dossier_items),
            selectinload(Module.documents).selectinload(Document.procedure_steps),
            selectinload(Module.documents).selectinload(Document.attachments),
        )
        .join(Department)
        .where(Department.code == department_id, Module.code == module_code)
    )
    if module is None or not is_indexable(
        is_active=module.is_active,
        release_status=module.release_status,
        environment=environment,
    ):
        return []

    chunks: list[GoldChunk] = []
    for faq in module.faqs:
        if not is_indexable(
            is_active=faq.is_active,
            release_status=faq.release_status,
            environment=environment,
        ):
            continue
        markdown = serialize_faq(
            question=faq.question,
            question_code=faq.question_code,
            answer=faq.answer,
            legal_basis=faq.legal_basis,
            category=faq.category,
            subcategory=faq.subcategory,
            release_status=faq.release_status,
            source_file=faq.source_file,
            source_sheet=faq.source_sheet,
            source_row=faq.source_row,
        )
        chunks.append(
            _chunk(
                department_id=department_id,
                module_code=module_code,
                entity_type="faq",
                business_key=faq.question_code,
                markdown=markdown,
                payload={
                    "question_code": faq.question_code,
                    "document_code": None,
                    "section_id": str(faq.id),
                    "has_legal_basis": bool(faq.legal_basis),
                    "source_file": faq.source_file,
                    "source_sheet": faq.source_sheet,
                    "source_row": faq.source_row,
                    "release_status": faq.release_status,
                    "effective_from": None,
                    "effective_to": None,
                    "citation_url": None,
                },
            )
        )

    for document in module.documents:
        if not is_indexable(
            is_active=document.is_active,
            release_status=document.release_status,
            environment=environment,
        ):
            continue
        chunks.extend(_document_chunks(department_id, module_code, document))
    return chunks


def _document_chunks(department_id: str, module_code: str, document: Document) -> list[GoldChunk]:
    regulations = [
        item for item in document.sections if item.is_active and item.section_type == "regulation"
    ]
    conditions = [
        item for item in document.sections if item.is_active and item.section_type != "regulation"
    ]
    assigned: set[str] = set()
    chunks: list[GoldChunk] = []
    citation = next((item.source_url for item in document.attachments if item.is_active), None)

    for section in sorted(regulations, key=lambda item: item.source_order or 0):
        related = [item for item in conditions if headings_related(section.heading, item.scenario)]
        for item in related:
            assigned.add(item.section_key)
        markdown = serialize_regulation(
            document_title=document.title,
            document_code=document.document_code,
            heading=section.heading,
            subheading=section.subheading,
            content=section.content,
            inline_condition=section.condition,
            resolution=section.resolution,
            related_conditions=_condition_tuples(related),
            release_status=document.release_status,
            source_file=section.source_file,
            source_sheet=section.source_sheet,
            source_row=section.source_row,
        )
        chunks.append(
            _section_chunk(
                department_id,
                module_code,
                document,
                section,
                "regulation",
                markdown,
                citation,
            )
        )

    for section in conditions:
        if section.section_key in assigned:
            continue
        markdown = serialize_condition(
            document_title=document.title,
            document_code=document.document_code,
            condition_type=section.section_type,
            scenario=section.scenario,
            resolution=section.resolution,
            release_status=document.release_status,
            source_file=section.source_file,
            source_sheet=section.source_sheet,
            source_row=section.source_row,
        )
        chunks.append(
            _section_chunk(
                department_id,
                module_code,
                document,
                section,
                "condition",
                markdown,
                citation,
            )
        )

    if document.procedure is not None and document.procedure.is_active:
        procedure = document.procedure
        leftover = [item for item in conditions if item.section_key not in assigned]
        related = leftover if not regulations else leftover
        markdown = serialize_procedure(
            document_title=document.title,
            document_code=document.document_code,
            summary=document.summary,
            result=procedure.result,
            processing_time_type=procedure.processing_time_type,
            max_working_days=procedure.max_working_days,
            location=procedure.location,
            submission_url=procedure.submission_url,
            special_schedule=procedure.special_schedule,
            fee_type=procedure.fee_type,
            fee_amount_vnd=procedure.fee_amount_vnd,
            fee_note=procedure.fee_note,
            answer_policy=procedure.answer_policy,
            related_conditions=_condition_tuples(related),
            release_status=document.release_status,
            effective_from=document.effective_from,
            effective_to=document.effective_to,
            source_file=procedure.source_file,
            source_sheet=procedure.source_sheet,
            source_row=procedure.source_row,
        )
        chunks.append(
            _chunk(
                department_id=department_id,
                module_code=module_code,
                entity_type="procedure",
                business_key=f"{document.document_code}|procedure",
                markdown=markdown,
                payload=_document_payload(document, str(procedure.id), citation),
            )
        )

    active_items = [item for item in document.dossier_items if item.is_active]
    if active_items:
        first = active_items[0]
        markdown = serialize_dossier(
            document_title=document.title,
            document_code=document.document_code,
            items=[
                (item.name, item.form_url, item.quantity_specification, item.is_required)
                for item in sorted(active_items, key=lambda row: row.source_order)
            ],
            release_status=document.release_status,
            source_file=first.source_file,
            source_sheet=first.source_sheet,
            source_row=first.source_row,
        )
        chunks.append(
            _chunk(
                department_id=department_id,
                module_code=module_code,
                entity_type="dossier",
                business_key=f"{document.document_code}|dossier",
                markdown=markdown,
                payload=_document_payload(document, str(first.id), citation),
            )
        )

    for step in sorted(
        (item for item in document.procedure_steps if item.is_active),
        key=lambda row: row.step_number,
    ):
        markdown = serialize_step(
            document_title=document.title,
            document_code=document.document_code,
            step_number=step.step_number,
            instruction=step.instruction,
            time_requirement=step.time_requirement,
            url_or_location=step.url_or_location,
            responsible_unit=step.responsible_unit,
            channel=step.channel,
            release_status=document.release_status,
            source_file=step.source_file,
            source_sheet=step.source_sheet,
            source_row=step.source_row,
        )
        chunks.append(
            _chunk(
                department_id=department_id,
                module_code=module_code,
                entity_type="step",
                business_key=f"{document.document_code}|step|{step.step_number}",
                markdown=markdown,
                payload=_document_payload(document, str(step.id), citation),
            )
        )
    return chunks


def _condition_tuples(
    sections: Sequence[DocumentSection],
) -> list[tuple[str | None, str | None, str | None]]:
    return [(item.section_type, item.scenario, item.resolution) for item in sections]


def _section_chunk(
    department_id: str,
    module_code: str,
    document: Document,
    section: DocumentSection,
    entity_type: GoldEntityType,
    markdown: str,
    citation: str | None,
) -> GoldChunk:
    return _chunk(
        department_id=department_id,
        module_code=module_code,
        entity_type=entity_type,
        business_key=f"{document.document_code}|{section.section_key}",
        markdown=markdown,
        payload=_document_payload(document, str(section.id), citation)
        | {
            "section_type": section.section_type,
            "source_file": section.source_file,
            "source_sheet": section.source_sheet,
            "source_row": section.source_row,
        },
    )


def _document_payload(
    document: Document, section_id: str, citation: str | None
) -> dict[str, object]:
    return {
        "document_code": document.document_code,
        "document_id": str(document.id),
        "section_id": section_id,
        "release_status": document.release_status,
        "effective_from": document.effective_from.isoformat() if document.effective_from else None,
        "effective_to": document.effective_to.isoformat() if document.effective_to else None,
        "citation_url": citation,
        "source_file": document.source_file,
        "source_sheet": document.source_sheet,
        "source_row": document.source_row,
    }


def _chunk(
    *,
    department_id: str,
    module_code: str,
    entity_type: GoldEntityType,
    business_key: str,
    markdown: str,
    payload: dict[str, object],
) -> GoldChunk:
    chunk_id = gold_chunk_id(department_id, module_code, entity_type, business_key)
    markdown = redact_contact_text(markdown)
    digest = content_hash(markdown)
    return GoldChunk(
        chunk_id=chunk_id,
        point_id=str(point_uuid(chunk_id)),
        entity_type=entity_type,
        stair_markdown=markdown,
        content_hash=digest,
        payload={
            "chunk_id": chunk_id,
            "department_id": department_id,
            "module_code": module_code,
            "entity_type": entity_type,
            "is_active": True,
            "content_hash": digest,
            "stair_markdown": markdown,
            **payload,
        },
    )
