class IngestionError(Exception):
    """Base error for the Bronze ingestion pipeline."""


class ManifestError(IngestionError):
    """Release manifest is missing, malformed or inconsistent."""


class SchemaDriftError(IngestionError):
    """Workbook structure no longer matches the locked schema fingerprint."""


class ChecksumMismatchError(IngestionError):
    """Source file bytes do not match the release manifest."""


class AdapterNotImplementedError(IngestionError):
    """Requested source adapter is not available in this phase."""
