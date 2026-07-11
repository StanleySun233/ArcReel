"""Alembic backfill migration tests for custom model supported durations."""

from __future__ import annotations

from pathlib import Path

import pytest

from alembic import command
from tests.alembic_pg import AlembicPostgresDb

pytest_plugins = ["tests.alembic_pg"]


@pytest.fixture
def backfill_revisions() -> tuple[str, str]:
    repo_root = Path(__file__).resolve().parent.parent
    versions_dir = repo_root / "alembic" / "versions"
    matches = list(versions_dir.glob("*_backfill_custom_model_durations.py"))
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


def test_backfill_video_endpoints_with_null_durations(
    alembic_pg: AlembicPostgresDb, backfill_revisions: tuple[str, str]
):
    backfill_revision_id, parent_revision_id = backfill_revisions
    command.upgrade(alembic_pg.cfg, parent_revision_id)

    alembic_pg.execute(
        "INSERT INTO custom_provider "
        "(id, display_name, discovery_format, base_url, api_key, created_at, updated_at) "
        "VALUES (1, 'P', 'openai', 'https://x', 'k', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    alembic_pg.execute(
        "INSERT INTO custom_provider_model "
        "(id, provider_id, model_id, display_name, endpoint, is_default, is_enabled, "
        "supported_durations, created_at, updated_at) VALUES "
        "(1, 1, 'sora-2-pro', 'X', 'openai-video', FALSE, TRUE, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),"
        "(2, 1, 'unknown-foo', 'Y', 'openai-video', FALSE, TRUE, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),"
        "(3, 1, 'gpt-4o', 'Z', 'openai-chat', FALSE, TRUE, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),"
        "(4, 1, 'sora-2', 'W', 'openai-video', FALSE, TRUE, '[1,2,3]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )

    command.upgrade(alembic_pg.cfg, backfill_revision_id)

    rows = alembic_pg.fetchall("SELECT model_id, supported_durations FROM custom_provider_model ORDER BY id")
    by_id = {r[0]: r[1] for r in rows}

    assert by_id["sora-2-pro"] == "[4, 8, 12]"
    assert by_id["unknown-foo"] == "[4, 8]"
    assert by_id["gpt-4o"] is None
    assert by_id["sora-2"] == "[1,2,3]"
