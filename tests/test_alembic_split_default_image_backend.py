"""Alembic split_default_image_backend_setting migration tests."""

from __future__ import annotations

from alembic import command

from tests.alembic_pg import AlembicPostgresDb, alembic_pg  # noqa: F401

TENANT_SETTINGS = {"app.current_tenant_id": "ten_default", "app.current_user_id": "default"}


def test_upgrade_copies_legacy_setting_to_two_new_keys(alembic_pg: AlembicPostgresDb):
    command.upgrade(alembic_pg.cfg, "eedf0aa985e6")

    alembic_pg.execute(
        "INSERT INTO system_setting (key, value, updated_at) "
        "VALUES ('default_image_backend', 'openai/gpt-image-1', CURRENT_TIMESTAMP)"
    )

    command.upgrade(alembic_pg.cfg, "head")

    rows = alembic_pg.fetchall_with_settings(
        TENANT_SETTINGS,
        "SELECT key, value FROM system_setting WHERE key IN "
        "('default_image_backend', 'default_image_backend_t2i', 'default_image_backend_i2i')"
    )
    settings = {r.key: r.value for r in rows}
    assert settings.get("default_image_backend_t2i") == "openai/gpt-image-1"
    assert settings.get("default_image_backend_i2i") == "openai/gpt-image-1"
    assert settings.get("default_image_backend") == "openai/gpt-image-1"


def test_upgrade_preserves_already_set_new_keys(alembic_pg: AlembicPostgresDb):
    command.upgrade(alembic_pg.cfg, "eedf0aa985e6")

    alembic_pg.execute(
        "INSERT INTO system_setting (key, value, updated_at) "
        "VALUES ('default_image_backend', 'openai/legacy', CURRENT_TIMESTAMP), "
        "('default_image_backend_t2i', 'openai/already-set', CURRENT_TIMESTAMP)"
    )

    command.upgrade(alembic_pg.cfg, "head")

    rows = alembic_pg.fetchall_with_settings(
        TENANT_SETTINGS,
        "SELECT key, value FROM system_setting WHERE key IN "
        "('default_image_backend_t2i', 'default_image_backend_i2i')"
    )
    settings = {r.key: r.value for r in rows}
    assert settings.get("default_image_backend_t2i") == "openai/already-set"
    assert settings.get("default_image_backend_i2i") == "openai/legacy"


def test_upgrade_no_op_when_no_legacy(alembic_pg: AlembicPostgresDb):
    command.upgrade(alembic_pg.cfg, "head")

    rows = alembic_pg.fetchall_with_settings(
        TENANT_SETTINGS,
        "SELECT key FROM system_setting WHERE key IN "
        "('default_image_backend', 'default_image_backend_t2i', 'default_image_backend_i2i')"
    )
    assert rows == []


def test_downgrade_drops_only_new_keys(alembic_pg: AlembicPostgresDb):
    command.upgrade(alembic_pg.cfg, "head")

    alembic_pg.execute_with_settings(
        TENANT_SETTINGS,
        "INSERT INTO system_setting (tenant_id, user_id, key, value, updated_at) "
        "VALUES ('ten_default', 'default', 'default_image_backend', 'openai/legacy', CURRENT_TIMESTAMP), "
        "('ten_default', 'default', 'default_image_backend_t2i', 'openai/t2i', CURRENT_TIMESTAMP), "
        "('ten_default', 'default', 'default_image_backend_i2i', 'openai/i2i', CURRENT_TIMESTAMP)"
    )

    command.downgrade(alembic_pg.cfg, "eedf0aa985e6")

    rows = alembic_pg.fetchall(
        "SELECT key FROM system_setting WHERE key IN "
        "('default_image_backend', 'default_image_backend_t2i', 'default_image_backend_i2i')"
    )
    keys = {r.key for r in rows}
    assert keys == {"default_image_backend"}
