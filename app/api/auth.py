import secrets
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from app.ingestion.exceptions import ManifestError
from app.ingestion.manifest import (
    DepartmentConfig,
    DepartmentModuleConfig,
    load_department_configs,
    resolve_module,
)

_API_KEY = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True)
class Principal:
    id: str
    department_id: str
    modules: tuple[str, ...]


async def authenticate(request: Request, x_api_key: str = Security(_API_KEY)) -> Principal:
    x_api_key = x_api_key or ""
    settings = request.app.state.settings
    matches = []
    for client in settings.api_clients:
        if secrets.compare_digest(x_api_key.encode(), client.api_key.get_secret_value().encode()):
            matches.append(Principal(client.id, client.department_id, tuple(client.modules)))
    # Compatibility key grants only the explicitly configured legacy context.
    if not settings.api_clients and secrets.compare_digest(
        x_api_key.encode(), settings.app_api_key.get_secret_value().encode()
    ):
        matches.append(Principal("legacy", settings.app_department_id, (settings.app_module_code,)))
    if len(matches) != 1:
        raise HTTPException(401, "Invalid API key")
    return matches[0]


def authorized_module(
    request: Request, principal: Principal, module_code: str | None
) -> tuple[DepartmentConfig, DepartmentModuleConfig]:
    if module_code is None:
        if len(principal.modules) != 1:
            raise HTTPException(422, "Select module_code")
        module_code = principal.modules[0]
    if module_code not in principal.modules:
        raise HTTPException(403, "Module access denied")
    try:
        return resolve_module(
            load_department_configs(Path(request.app.state.settings.departments_config_path)),
            principal.department_id,
            module_code,
        )
    except (ValueError, ManifestError):
        raise HTTPException(403, "Unknown or disabled module") from None
