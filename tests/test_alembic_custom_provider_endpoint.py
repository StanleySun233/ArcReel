"""Alembic 0426endpointrefactor migration tests."""

from __future__ import annotations

from alembic import command
from tests.alembic_pg import AlembicPostgresDb

pytest_plugins = ["tests.alembic_pg"]


def _seed_pre_endpoint_state(db: AlembicPostgresDb, combos: list[tuple[str, str]]) -> None:
    for i, (api_fmt, media) in enumerate(combos, start=1):
        db.execute(
            "INSERT INTO custom_provider (id, display_name, api_format, base_url, api_key, created_at, updated_at) "
            "VALUES (:id, :name, :api_format, :base_url, :api_key, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            {"id": i, "name": f"P{i}", "api_format": api_fmt, "base_url": "https://x", "api_key": "k"},
        )
        db.execute(
            "INSERT INTO custom_provider_model "
            "(provider_id, model_id, display_name, media_type, is_default, is_enabled, created_at, updated_at) "
            "VALUES (:provider_id, :model_id, :display_name, :media_type, FALSE, TRUE, "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            {"provider_id": i, "model_id": f"m-{i}", "display_name": f"m-{i}", "media_type": media},
        )


def test_upgrade_maps_all_nine_combos(alembic_pg: AlembicPostgresDb):
    command.upgrade(alembic_pg.cfg, "a89021f43d52")

    combos = [
        ("openai", "text"),
        ("openai", "image"),
        ("openai", "video"),
        ("google", "text"),
        ("google", "image"),
        ("google", "video"),
        ("newapi", "text"),
        ("newapi", "image"),
        ("newapi", "video"),
    ]
    _seed_pre_endpoint_state(alembic_pg, combos)

    command.upgrade(alembic_pg.cfg, "0426endpointrefactor")

    expected_endpoints = [
        "openai-chat",
        "openai-images",
        "openai-video",
        "gemini-generate",
        "gemini-image",
        "openai-video",
        "openai-chat",
        "openai-images",
        "newapi-video",
    ]
    expected_discovery = [
        "openai",
        "openai",
        "openai",
        "google",
        "google",
        "google",
        "openai",
        "openai",
        "openai",
    ]

    for i, endpoint in enumerate(expected_endpoints, start=1):
        row = alembic_pg.fetchall(
            "SELECT endpoint FROM custom_provider_model WHERE provider_id = :provider_id",
            {"provider_id": i},
        )[0]
        assert row.endpoint == endpoint

    for i, discovery_format in enumerate(expected_discovery, start=1):
        row = alembic_pg.fetchall(
            "SELECT discovery_format FROM custom_provider WHERE id = :id",
            {"id": i},
        )[0]
        assert row.discovery_format == discovery_format


def test_downgrade_restores_columns(alembic_pg: AlembicPostgresDb):
    command.upgrade(alembic_pg.cfg, "0426endpointrefactor")

    alembic_pg.execute(
        "INSERT INTO custom_provider (id, display_name, discovery_format, base_url, api_key, created_at, updated_at) "
        "VALUES (1, 'P', 'openai', 'https://x', 'k', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    alembic_pg.execute(
        "INSERT INTO custom_provider_model "
        "(provider_id, model_id, display_name, endpoint, is_default, is_enabled, created_at, updated_at) "
        "VALUES (1, 'sora-2', 'Sora 2', 'openai-video', FALSE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )

    command.downgrade(alembic_pg.cfg, "a89021f43d52")

    row = alembic_pg.fetchall("SELECT api_format FROM custom_provider WHERE id = 1")[0]
    assert row.api_format == "openai"
    row = alembic_pg.fetchall("SELECT media_type FROM custom_provider_model WHERE provider_id = 1")[0]
    assert row.media_type == "video"
