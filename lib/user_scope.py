from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
from urllib.parse import quote

from lib.db.base import DEFAULT_USER_ID

_current_user_id: ContextVar[str | None] = ContextVar("arcreel_current_user_id", default=None)
_current_tenant_id: ContextVar[str | None] = ContextVar("arcreel_current_tenant_id", default=None)


def set_current_user_id(user_id: str | None) -> None:
    _current_user_id.set(user_id or DEFAULT_USER_ID)


def get_current_user_id() -> str:
    return _current_user_id.get() or DEFAULT_USER_ID


def set_current_tenant_id(tenant_id: str | None) -> None:
    _current_tenant_id.set(tenant_id)


def get_current_tenant_id() -> str | None:
    return _current_tenant_id.get()


def scoped_projects_root(base_root: Path) -> Path:
    tenant_id = get_current_tenant_id()
    if tenant_id:
        return tenant_projects_root(base_root, tenant_id)
    user_id = get_current_user_id()
    if user_id == DEFAULT_USER_ID:
        return base_root
    return base_root / "_users" / quote(user_id, safe="") / "projects"


def tenant_projects_root(base_root: Path, tenant_id: str) -> Path:
    normalized = quote((tenant_id or DEFAULT_USER_ID).strip() or DEFAULT_USER_ID, safe="")
    return base_root / "_tenants" / normalized / "projects"
