from __future__ import annotations

import json
from pathlib import Path

from app.ingestion.models import ValidationReport


def write_json_report(report: ValidationReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def render_markdown(report: ValidationReport) -> str:
    lines = [
        f"# Validation report — {report.release_id}",
        "",
        f"- Department: `{report.department_id}`",
        f"- Module: `{report.module_code}`",
        f"- Dry-run: `{report.dry_run}`",
        f"- Publish allowed: `{report.publish_allowed}`",
        f"- Blocked: `{report.blocked}`",
        f"- Errors: {report.error_count}",
        f"- Warnings: {report.warning_count}",
        f"- Infos: {report.info_count}",
        "",
        "## Counts",
        "",
        "| Entity | Actual | Expected |",
        "|---|---:|---:|",
    ]
    expected = report.expected_counts.model_dump() if report.expected_counts else {}
    for key, actual in report.counts.model_dump().items():
        lines.append(f"| `{key}` | {actual} | {expected.get(key, '')} |")
    lines.extend(["", "## Policy findings (DATA-01 to DATA-10)", ""])
    for finding in report.policy_findings:
        count = f" ({finding.count})" if finding.count is not None else ""
        lines.append(f"- `{finding.id}` [{finding.severity.upper()}]{count}: {finding.message}")
    lines.extend(["", "## Issues", ""])
    if not report.issues:
        lines.append("Không có issue.")
    for issue in report.issues:
        location = ""
        if issue.source_file:
            location = f" `{issue.source_file}`"
            if issue.source_sheet:
                location += f" / `{issue.source_sheet}`"
            if issue.source_row:
                location += f" / row {issue.source_row}"
            if issue.source_column:
                location += f" / {issue.source_column}"
        lines.append(f"- **{issue.severity.upper()}** `{issue.code}`{location}: {issue.message}")
    lines.append("")
    return "\n".join(lines)


def write_markdown_report(report: ValidationReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report), encoding="utf-8")
    return path
