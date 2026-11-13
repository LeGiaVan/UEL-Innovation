from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.models import FaqMatch
from app.gold.models import GoldHit
from app.gold.policy import allowed_release_statuses
from app.ingestion.contact import ContactConfig, ResolvedContact, resolve_contact
from app.ingestion.normalize import normalize_question
from app.models.tables import Department, Faq, Module


class FaqStore(Protocol):
    def match_normalized(
        self,
        *,
        department_id: str,
        module_code: str,
        normalized_question: str,
        environment: str,
    ) -> FaqMatch | None: ...

    def sample_questions(
        self,
        *,
        department_id: str,
        module_code: str,
        environment: str,
        limit: int = 6,
    ) -> list[str]: ...

    def load_contact(
        self,
        *,
        department_id: str,
        module_code: str,
        environment: str,
    ) -> ResolvedContact: ...


class Retriever(Protocol):
    def search(
        self,
        query: str,
        *,
        department_id: str,
        module_code: str,
        environment: str,
        limit: int = 8,
        mode: str = "hybrid",
        faq_boost: float | None = None,
    ) -> list[GoldHit]: ...


class SilverFaqStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def match_normalized(
        self,
        *,
        department_id: str,
        module_code: str,
        normalized_question: str,
        environment: str,
    ) -> FaqMatch | None:
        allowed = allowed_release_statuses(environment)
        with self._session_factory() as session:
            row = session.scalar(
                select(Faq)
                .join(Department, Faq.department_id == Department.id)
                .join(Module, Faq.module_id == Module.id)
                .where(
                    Department.code == department_id,
                    Module.code == module_code,
                    Faq.is_active.is_(True),
                    Module.is_active.is_(True),
                    Department.is_active.is_(True),
                    Module.release_status.in_(allowed),
                    Faq.release_id == Module.release_id,
                    Faq.release_status.in_(allowed),
                    Faq.normalized_question == normalized_question,
                )
            )
            if row is None:
                return None
            return FaqMatch(
                question_code=row.question_code,
                question=row.question,
                answer=row.answer,
                legal_basis=row.legal_basis,
            )

    def sample_questions(
        self,
        *,
        department_id: str,
        module_code: str,
        environment: str,
        limit: int = 6,
    ) -> list[str]:
        allowed = allowed_release_statuses(environment)
        with self._session_factory() as session:
            rows = session.scalars(
                select(Faq.question)
                .join(Department, Faq.department_id == Department.id)
                .join(Module, Faq.module_id == Module.id)
                .where(
                    Department.code == department_id,
                    Module.code == module_code,
                    Faq.is_active.is_(True),
                    Module.is_active.is_(True),
                    Department.is_active.is_(True),
                    Module.release_status.in_(allowed),
                    Faq.release_id == Module.release_id,
                    Faq.release_status.in_(allowed),
                )
                .order_by(Faq.source_order, Faq.question_code)
                .limit(limit)
            ).all()
        return [str(item) for item in rows]

    def load_contact(
        self,
        *,
        department_id: str,
        module_code: str,
        environment: str,
    ) -> ResolvedContact:
        allow_unverified = environment in {"development", "test"}
        with self._session_factory() as session:
            module = session.scalar(
                select(Module)
                .join(Department, Module.department_id == Department.id)
                .where(Department.code == department_id, Module.code == module_code)
            )
            department = session.scalar(select(Department).where(Department.code == department_id))
            module_contact = ContactConfig(
                support_contact=module.support_contact if module else None,
                contact_information=module.contact_information if module else None,
                online_channel=module.online_channel if module else None,
                verified=bool(module.contact_verified) if module else False,
            )
            department_contact = ContactConfig(
                support_contact=department.support_contact if department else None,
                contact_information=department.contact_information if department else None,
                online_channel=department.online_channel if department else None,
                verified=bool(department.contact_verified) if department else False,
            )
        return resolve_contact(
            record_support=None,
            record_information=None,
            record_channel=None,
            module=module_contact,
            department=department_contact,
            allow_unverified_inheritance=allow_unverified,
        )


class MemoryFaqStore:
    def __init__(
        self,
        faqs: Sequence[FaqMatch] | None = None,
        contact: ResolvedContact | None = None,
    ) -> None:
        self._faqs = list(faqs or [])
        self.contact = contact or ResolvedContact(
            support_contact="Phòng Bảo đảm chất lượng",
            source="department",
            verified=False,
        )

    def match_normalized(
        self,
        *,
        department_id: str,
        module_code: str,
        normalized_question: str,
        environment: str,
    ) -> FaqMatch | None:
        del department_id, module_code, environment
        for item in self._faqs:
            if normalize_question(item.question) == normalized_question:
                return item
        return None

    def sample_questions(
        self,
        *,
        department_id: str,
        module_code: str,
        environment: str,
        limit: int = 6,
    ) -> list[str]:
        del department_id, module_code, environment
        return [item.question for item in self._faqs[:limit]]

    def load_contact(
        self,
        *,
        department_id: str,
        module_code: str,
        environment: str,
    ) -> ResolvedContact:
        del department_id, module_code, environment
        return self.contact


class MemoryRetriever:
    def __init__(self, hits: Sequence[GoldHit] | None = None) -> None:
        self.hits = list(hits or [])
        self.calls: list[str] = []

    def search(
        self,
        query: str,
        *,
        department_id: str,
        module_code: str,
        environment: str,
        limit: int = 8,
        mode: str = "hybrid",
        faq_boost: float | None = None,
    ) -> list[GoldHit]:
        del department_id, module_code, environment, mode, faq_boost
        self.calls.append(query)
        return list(self.hits[:limit])
