from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    id: str
    username: str
    system_admin: bool


@dataclass(frozen=True)
class DepartmentContext:
    user: Principal
    department: str
    role: str
