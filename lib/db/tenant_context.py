from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_tenant_context(session: AsyncSession, *, user_id: str, tenant_id: str) -> None:
    await session.execute(
        text(
            "SELECT "
            "set_config('app.current_user_id', :user_id, true), "
            "set_config('app.current_tenant_id', :tenant_id, true), "
            "set_config('app.auth_mode', 'tenant', true)"
        ),
        {"user_id": user_id, "tenant_id": tenant_id},
    )
