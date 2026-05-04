"""Read-only permission catalog for dynamic admin UI (grouped by module)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.db.session import get_db
from app.models.permission import Permission
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/permissions", tags=["permissions"])


class PermissionItem(BaseModel):
    code: str
    display_name: str


class PermissionModuleGroup(BaseModel):
    module: str
    permissions: list[PermissionItem]


@router.get("", response_model=list[PermissionModuleGroup])
def list_permissions_grouped(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_admin)],
) -> list[PermissionModuleGroup]:
    """Return all catalog permissions grouped by module (DB-driven; no hardcoded matrix)."""
    rows = db.scalars(select(Permission).order_by(Permission.module.asc(), Permission.code.asc())).all()
    by_module: dict[str, list[PermissionItem]] = {}
    for row in rows:
        by_module.setdefault(row.module, []).append(
            PermissionItem(code=row.code, display_name=row.display_name)
        )
    return [
        PermissionModuleGroup(module=module, permissions=items)
        for module, items in sorted(by_module.items(), key=lambda x: x[0])
    ]
