"""Tests for lib.db.engine configuration."""

import os
from unittest.mock import patch

import pytest

from lib.db.engine import get_database_url, is_sqlite_backend


class TestGetDatabaseUrl:
    def test_missing_database_url_is_rejected(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATABASE_URL", None)
            with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
                get_database_url()

    def test_sqlite_database_url_is_rejected(self):
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite+aiosqlite:///./projects/.arcreel.db"}):
            with pytest.raises(RuntimeError, match="postgresql\\+asyncpg"):
                get_database_url()

    def test_postgresql_database_url_is_accepted(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql+asyncpg://localhost/test"}):
            url = get_database_url()
            assert url == "postgresql+asyncpg://localhost/test"


class TestIsSqliteBackend:
    def test_postgresql(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql+asyncpg://localhost/test"}):
            assert is_sqlite_backend() is False
