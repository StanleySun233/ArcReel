from pathlib import Path


def test_canonical_db_runtime_entrypoints_do_not_create_sqlite_databases():
    for relative in (
        "tests/conftest.py",
        "tests/agent_session_store/conftest.py",
        "alembic/env.py",
    ):
        text = Path(relative).read_text(encoding="utf-8")
        assert "sqlite+aiosqlite" not in text
