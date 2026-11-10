from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import Department, Faq, Module

CASES_PATH = Path("evaluation/cases.yaml")

EvalKind = Literal["retrieval", "policy", "adversarial", "tenant_leak"]
EvalSplit = Literal["calibration", "test"]


class EvalCase(BaseModel):
    id: str
    query: str
    kind: EvalKind
    split: EvalSplit
    expected_question_codes: list[str] = Field(default_factory=list)
    expected_document_codes: list[str] = Field(default_factory=list)
    must_contain: list[str] = Field(default_factory=list)
    expect_empty: bool = False
    exact_match_eligible: bool = False
    expected_policy: str | None = None


def load_authored_cases(path: Path = CASES_PATH) -> list[EvalCase]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [EvalCase.model_validate(item) for item in payload["cases"]]


def faq_cases_from_silver(
    session: Session,
    *,
    department_id: str | None = None,
    module_code: str | None = None,
) -> list[EvalCase]:
    query = select(Faq).where(Faq.is_active.is_(True))
    if department_id is not None or module_code is not None:
        query = query.join(Department, Faq.department_id == Department.id).join(
            Module, Faq.module_id == Module.id
        )
        if department_id is not None:
            query = query.where(Department.code == department_id)
        if module_code is not None:
            query = query.where(Module.code == module_code)
    query = query.order_by(Faq.question_code)
    rows = session.scalars(query).all()
    cases: list[EvalCase] = []
    for faq in rows:
        digest = hashlib.sha256(faq.question_code.encode("utf-8")).digest()[0]
        split: EvalSplit = "test" if digest % 3 == 0 else "calibration"
        cases.append(
            EvalCase(
                id=f"faq-verbatim-{faq.question_code}",
                query=faq.question,
                kind="retrieval",
                split=split,
                expected_question_codes=[faq.question_code],
                exact_match_eligible=True,
            )
        )
    return cases


def load_eval_cases(
    session: Session | None,
    path: Path = CASES_PATH,
    *,
    department_id: str | None = None,
    module_code: str | None = None,
) -> list[EvalCase]:
    authored = load_authored_cases(path)
    generated = (
        faq_cases_from_silver(session, department_id=department_id, module_code=module_code)
        if session is not None
        else []
    )
    by_id = {case.id: case for case in generated}
    by_id.update({case.id: case for case in authored})
    return sorted(by_id.values(), key=lambda item: item.id)


def dataset_fingerprint(cases: list[EvalCase]) -> str:
    payload = "\n".join(f"{item.id}|{item.split}|{item.query}" for item in cases)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
