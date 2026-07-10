from sqlalchemy import text

from lib.db.tenant_context import set_tenant_context


async def test_set_tenant_context_sets_local_postgres_settings(async_session):
    async with async_session.begin():
        await set_tenant_context(async_session, user_id="camel:u1", tenant_id="ten_a")
        user_id = await async_session.scalar(text("SELECT current_setting('app.current_user_id', true)"))
        tenant_id = await async_session.scalar(text("SELECT current_setting('app.current_tenant_id', true)"))
        auth_mode = await async_session.scalar(text("SELECT current_setting('app.auth_mode', true)"))

    assert user_id == "camel:u1"
    assert tenant_id == "ten_a"
    assert auth_mode == "tenant"
