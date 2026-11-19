from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Issue:
    level: str
    message: str
    file: str = ""
    code: str = ""
    ref: str = ""
    raw: str = ""
    mapped: str = ""

    def as_dict(self) -> dict[str, str]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value or key in {"level", "message", "file"}}


@dataclass
class IssueLog:
    items: list[Issue] = field(default_factory=list)

    def error(
        self,
        message: str,
        file: str = "",
        *,
        code: str = "",
        ref: str = "",
        raw: str = "",
        mapped: str = "",
    ) -> None:
        self.items.append(Issue("ERROR", message, file, code, ref, raw, mapped))

    def warning(
        self,
        message: str,
        file: str = "",
        *,
        code: str = "",
        ref: str = "",
        raw: str = "",
        mapped: str = "",
    ) -> None:
        self.items.append(Issue("WARNING", message, file, code, ref, raw, mapped))

    @property
    def errors(self) -> list[str]:
        return [i.message for i in self.items if i.level == "ERROR"]

    @property
    def warnings(self) -> list[str]:
        return [i.message for i in self.items if i.level == "WARNING"]

    def as_dicts(self) -> list[dict[str, str]]:
        return [item.as_dict() for item in self.items]

    def payload(self) -> dict:
        return {
            "errors": self.errors,
            "warnings": self.warnings,
            "issues": self.as_dicts(),
        }

    @property
    def ok(self) -> bool:
        return not self.errors
