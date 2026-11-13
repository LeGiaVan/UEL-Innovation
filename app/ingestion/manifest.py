from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from app.ingestion.contact import ContactConfig
from app.ingestion.enums import WorkbookRole
from app.ingestion.exceptions import ManifestError


class ManifestFile(BaseModel):
    name: str
    role: WorkbookRole
    file_sha256: str
    schema_sha256: str


class ManifestCounts(BaseModel):
    routing_rules: int
    faqs: int
    documents: int
    regulation_sections: int
    condition_exception_sections: int
    dossier_items: int
    procedure_steps: int


class ReleaseManifest(BaseModel):
    schema_version: str
    release_id: str
    created_at: str
    department_id: str
    department_name: str
    module_code: str
    module_name: str
    source_type: str
    release_status: str
    files: list[ManifestFile]
    expected_counts: ManifestCounts
    allowed_environments: list[str] = Field(default_factory=list)
    prohibited_environments: list[str] = Field(default_factory=list)

    def file_for_role(self, role: WorkbookRole) -> ManifestFile:
        matches = [item for item in self.files if item.role == role]
        if len(matches) != 1:
            raise ManifestError(f"Release manifest must declare exactly one file for role {role}.")
        return matches[0]

    def schema_by_digest(self) -> dict[str, WorkbookRole]:
        return {item.schema_sha256: item.role for item in self.files}


class PromptPack(BaseModel):
    role: str = Field(default="", max_length=500)
    constraints: str = Field(default="", max_length=4000)
    glossary: dict[str, str] = Field(default_factory=dict)
    answer_style: str = Field(
        default="",
        max_length=2000,
        description="Per-module writing notes appended to the generate user prompt.",
    )
    metadata_system: str = Field(
        default="",
        max_length=4000,
        description="Optional LLM system text for topic/training-system metadata.",
    )

    @field_validator("glossary")
    @classmethod
    def _glossary_bounds(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 20:
            raise ValueError("glossary allows at most 20 terms")
        for key, term in value.items():
            if not key.strip() or len(key) > 64 or len(term) > 200:
                raise ValueError("glossary term keys ≤64 and values ≤200 characters")
        return value


class BotMessages(BaseModel):
    greeting: str = Field(default="", max_length=2000)
    out_of_scope: str = Field(default="", max_length=2000)
    clarification: str = Field(default="", max_length=2000)


class RetrievalSettings(BaseModel):
    top_k: int | None = Field(default=None, ge=1, le=20)
    score_threshold: float | None = Field(default=None, ge=0, le=1)
    mode: Literal["hybrid", "dense"] | None = None
    faq_boost: float | None = Field(default=None, ge=0, le=1)


class DepartmentModuleConfig(BaseModel):
    code: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    source_type: Literal["xlsx", "google-sheets"]
    source_path: str
    enabled: bool = True
    contact: ContactConfig = Field(default_factory=ContactConfig)
    profile: Literal["generic", "assessment"] = "generic"
    description: str = ""
    routing_aliases: dict[str, list[str]] = Field(default_factory=dict)
    prompt_pack: PromptPack = Field(default_factory=PromptPack)
    messages: BotMessages = Field(default_factory=BotMessages)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)


class DepartmentConfig(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    audience: str
    enabled: bool = True
    contact: ContactConfig = Field(default_factory=ContactConfig)
    modules: list[DepartmentModuleConfig]


def _require_mapping(payload: object, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ManifestError(f"{label} must be a mapping.")
    return payload


def load_release_manifest(path: Path) -> ReleaseManifest:
    if not path.is_file():
        raise ManifestError(f"Release manifest not found: {path}")
    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    data = _require_mapping(payload, "release-manifest.yaml")
    try:
        department = _require_mapping(data.get("department"), "department")
        module = _require_mapping(data.get("module"), "module")
        files = data.get("files") or []
        counts = _require_mapping(data.get("expected_counts"), "expected_counts")
        return ReleaseManifest(
            schema_version=str(data.get("schema_version") or ""),
            release_id=str(data.get("release_id") or ""),
            created_at=str(data.get("created_at") or ""),
            department_id=str(department.get("id") or ""),
            department_name=str(department.get("name") or ""),
            module_code=str(module.get("code") or ""),
            module_name=str(module.get("name") or ""),
            source_type=str(data.get("source_type") or ""),
            release_status=str(data.get("release_status") or ""),
            files=[ManifestFile.model_validate(item) for item in files],
            expected_counts=ManifestCounts.model_validate(counts),
            allowed_environments=list(data.get("allowed_environments") or []),
            prohibited_environments=list(data.get("prohibited_environments") or []),
        )
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"Invalid release manifest: {exc}") from exc


def load_department_configs(path: Path) -> list[DepartmentConfig]:
    if not path.is_file():
        raise ManifestError(f"Department config not found: {path}")
    with path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    data = _require_mapping(payload, str(path))
    departments = data.get("departments") or []
    parsed = [DepartmentConfig.model_validate(item) for item in departments]
    if len({d.id for d in parsed}) != len(parsed):
        raise ManifestError("Duplicate department IDs")
    for department in parsed:
        if len({m.code for m in department.modules}) != len(department.modules):
            raise ManifestError("Duplicate module codes")
    return parsed


def resolve_module(
    configs: list[DepartmentConfig],
    department_id: str,
    module_code: str,
) -> tuple[DepartmentConfig, DepartmentModuleConfig]:
    department = next((item for item in configs if item.id == department_id), None)
    if department is None or not department.enabled:
        raise ManifestError(f"Unknown or disabled department: {department_id}")
    module = next((item for item in department.modules if item.code == module_code), None)
    if module is None or not module.enabled:
        raise ManifestError(f"Unknown or disabled module: {department_id}/{module_code}")
    return department, module
