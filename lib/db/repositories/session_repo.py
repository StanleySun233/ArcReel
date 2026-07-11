"""Async repository for agent sessions."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import select, update

from lib.db.base import DEFAULT_USER_ID, dt_to_iso, utc_now
from lib.db.models.session import AgentSession
from lib.db.repositories.base import BaseRepository, rowcount
from lib.db.repositories.task_repo import DEFAULT_TENANT_ID


def _row_to_dict(row: AgentSession) -> dict[str, Any]:
    return {
        "id": row.id,
        "sdk_session_id": row.sdk_session_id,
        "tenant_id": row.tenant_id,
        "project_id": row.project_id,
        "title": row.title or "",
        "status": row.status,
        "created_at": dt_to_iso(row.created_at),
        "updated_at": dt_to_iso(row.updated_at),
    }


class SessionRepository(BaseRepository):
    def __init__(self, session, user_id: str | None = None, tenant_id: str | None = None):
        super().__init__(session)
        self.user_id = user_id or str(session.info.get("user_id") or DEFAULT_USER_ID)
        self.tenant_id = str(tenant_id or session.info.get("tenant_id") or DEFAULT_TENANT_ID)
        session.info["user_id"] = self.user_id
        session.info["tenant_id"] = self.tenant_id

    async def create(
        self, project_id: str, sdk_session_id: str, title: str = "", user_id: str | None = None
    ) -> dict[str, Any]:
        now = utc_now()
        row = AgentSession(
            id=uuid.uuid4().hex,
            sdk_session_id=sdk_session_id,
            project_id=project_id,
            title=title,
            status="idle",
            created_at=now,
            updated_at=now,
            user_id=user_id or self.user_id,
            tenant_id=self.tenant_id,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return _row_to_dict(row)

    async def get(self, session_id: str) -> dict[str, Any] | None:
        stmt = select(AgentSession).where(
            AgentSession.tenant_id == self.tenant_id,
            AgentSession.user_id == self.user_id,
            AgentSession.sdk_session_id == session_id,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return _row_to_dict(row) if row else None

    async def list(
        self,
        *,
        project_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        stmt = select(AgentSession).where(
            AgentSession.tenant_id == self.tenant_id, AgentSession.user_id == self.user_id
        )
        if project_id:
            stmt = stmt.where(AgentSession.project_id == project_id)
        if status:
            stmt = stmt.where(AgentSession.status == status)
        stmt = stmt.order_by(AgentSession.updated_at.desc())
        stmt = stmt.limit(max(1, limit)).offset(max(0, offset))
        result = await self.session.execute(stmt)
        return [_row_to_dict(row) for row in result.scalars().all()]

    async def update_status(self, session_id: str, status: str) -> bool:
        now = utc_now()
        result = await self.session.execute(
            update(AgentSession)
            .where(
                AgentSession.tenant_id == self.tenant_id,
                AgentSession.user_id == self.user_id,
                AgentSession.sdk_session_id == session_id,
            )
            .values(status=status, updated_at=now)
        )
        await self.session.commit()
        return rowcount(result) > 0

    async def delete(self, session_id: str) -> bool:
        result = await self.session.execute(
            sa_delete(AgentSession).where(
                AgentSession.tenant_id == self.tenant_id,
                AgentSession.user_id == self.user_id,
                AgentSession.sdk_session_id == session_id,
            )
        )
        await self.session.commit()
        return rowcount(result) > 0

    async def interrupt_running(self) -> int:
        now = utc_now()
        result = await self.session.execute(
            update(AgentSession)
            .where(
                AgentSession.tenant_id == self.tenant_id,
                AgentSession.user_id == self.user_id,
                AgentSession.status == "running",
            )
            .values(status="interrupted", updated_at=now)
        )
        await self.session.commit()
        return rowcount(result)
