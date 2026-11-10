from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.ingestion.enums import SourceType
from app.ingestion.exceptions import AdapterNotImplementedError
from app.ingestion.manifest import ReleaseManifest
from app.ingestion.models import ExtractionBundle, IdentifiedWorkbook

_GOOGLE_SHEETS_UNAVAILABLE = (
    "Google Sheets adapter shares the XLSX canonical model and is not implemented in Phase 2."
)


class SourceAdapter(ABC):
    source_type: SourceType

    @abstractmethod
    def list_workbooks(self, source_path: Path) -> list[Path]:
        raise NotImplementedError

    @abstractmethod
    def identify(
        self,
        source_path: Path,
        manifest: ReleaseManifest,
    ) -> list[IdentifiedWorkbook]:
        raise NotImplementedError

    @abstractmethod
    def extract(
        self,
        source_path: Path,
        manifest: ReleaseManifest,
        workbooks: list[IdentifiedWorkbook],
    ) -> ExtractionBundle:
        raise NotImplementedError


class GoogleSheetsAdapter(SourceAdapter):
    source_type = "google-sheets"

    def list_workbooks(self, source_path: Path) -> list[Path]:
        del source_path
        raise AdapterNotImplementedError(_GOOGLE_SHEETS_UNAVAILABLE)

    def identify(
        self,
        source_path: Path,
        manifest: ReleaseManifest,
    ) -> list[IdentifiedWorkbook]:
        del source_path, manifest
        raise AdapterNotImplementedError(_GOOGLE_SHEETS_UNAVAILABLE)

    def extract(
        self,
        source_path: Path,
        manifest: ReleaseManifest,
        workbooks: list[IdentifiedWorkbook],
    ) -> ExtractionBundle:
        del source_path, manifest, workbooks
        raise AdapterNotImplementedError(_GOOGLE_SHEETS_UNAVAILABLE)


def get_adapter(source_type: SourceType) -> SourceAdapter:
    from app.ingestion.xlsx_adapter import XlsxSourceAdapter

    if source_type == "xlsx":
        return XlsxSourceAdapter()
    if source_type == "google-sheets":
        return GoogleSheetsAdapter()
    raise AdapterNotImplementedError(f"Unsupported source type: {source_type}")
