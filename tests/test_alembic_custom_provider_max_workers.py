"""Alembic migration tests for custom_provider max worker columns."""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa

from alembic import command
from tests.alembic_pg import AlembicPostgresDb

pytest_plugins = ["tests.alembic_pg"]


@pytest.fixture
def revisions() -> tuple[str, str]:
    repo_root = Path(__file__).resolve().parent.parent
    versions_dir = repo_root / "alembic" / "versions"
    matches = list(versions_dir.glob("*_add_max_workers_columns_to_custom_.py"))
    assert len(matches) == 1
    text = matches[0].read_text(encoding="utf-8")
    revision: str | None = None
    down_revision: str | None = None
    for line in text.splitlines():
        if line.startswith("revision: str ="):
            revision = line.split("=")[1].strip().strip('"').strip("'")
        elif line.startswith("down_revision:"):
            down_revision = line.split("=")[1].strip().strip('"').strip("'")
    if not revision or not down_revision:
        raise RuntimeError("revision or down_revision was not found")
    return revision, down_revision


_COLS = ("image_max_workers", "video_max_workers", "audio_max_workers")


def test_upgrade_adds_columns_existing_row_null(alembic_pg: AlembicPostgresDb, revisions: tuple[str, str]):
    revision_id, parent_id = revisions
    command.upgrade(alembic_pg.cfg, parent_id)

    assert not (set(_COLS) & alembic_pg.columns("custom_provider"))
    alembic_pg.execute(
        "INSERT INTO custom_provider "
        "(id, display_name, discovery_format, base_url, api_key, created_at, updated_at) "
        "VALUES (1, 'P', 'openai', 'https://x', 'k', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )

    command.upgrade(alembic_pg.cfg, revision_id)

    assert set(_COLS) <= alembic_pg.columns("custom_provider")
    row = alembic_pg.fetchall(
        "SELECT image_max_workers, video_max_workers, audio_max_workers FROM custom_provider WHERE id = 1"
    )[0]
    assert row == (None, None, None)


@pytest.mark.parametrize("bad_value", [-1, 0])
@pytest.mark.parametrize("col", _COLS)
def test_upgrade_rejects_non_positive_workers(
    alembic_pg: AlembicPostgresDb, revisions: tuple[str, str], col: str, bad_value: int
):
    revision_id, _ = revisions
    command.upgrade(alembic_pg.cfg, revision_id)

    with pytest.raises(sa.exc.IntegrityError):
        alembic_pg.execute(
            "INSERT INTO custom_provider "
            f"(id, display_name, discovery_format, base_url, api_key, {col}, created_at, updated_at) "
            f"VALUES (1, 'P', 'openai', 'https://x', 'k', {bad_value}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )

    alembic_pg.execute(
        "INSERT INTO custom_provider "
        f"(id, display_name, discovery_format, base_url, api_key, {col}, created_at, updated_at) "
        "VALUES (2, 'P', 'openai', 'https://x', 'k', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    value = alembic_pg.scalar(f"SELECT {col} FROM custom_provider WHERE id = 2")
    assert value == 1


def test_downgrade_drops_columns(alembic_pg: AlembicPostgresDb, revisions: tuple[str, str]):
    revision_id, parent_id = revisions
    command.upgrade(alembic_pg.cfg, revision_id)

    alembic_pg.execute(
        "INSERT INTO custom_provider "
        "(id, display_name, discovery_format, base_url, api_key, image_max_workers, created_at, updated_at) "
        "VALUES (1, 'P', 'openai', 'https://x', 'k', 3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )

    command.downgrade(alembic_pg.cfg, parent_id)

    assert not (set(_COLS) & alembic_pg.columns("custom_provider"))
    name = alembic_pg.scalar("SELECT display_name FROM custom_provider WHERE id = 1")
    assert name == "P"
