import os
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7c1d2e3f4a5b"
down_revision: str | Sequence[str] | None = "f4a2c8d9e012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_APP_ROLE = "arcreel_app"
TABLE_PRIVILEGES = "SELECT, INSERT, UPDATE, DELETE"
SEQUENCE_PRIVILEGES = "USAGE, SELECT, UPDATE"


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _runtime_app_role() -> str:
    return os.environ.get("ARCREEL_DB_APP_ROLE", DEFAULT_APP_ROLE).strip()


def _schema_name() -> str | None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return None
    configured = op.get_context().version_table_schema
    if configured:
        return configured
    row = bind.execute(sa.text("SELECT current_schema()")).scalar()
    return str(row) if row else None


def _role_exists(role: str) -> bool:
    bind = op.get_bind()
    return bool(bind.execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}).scalar())


def upgrade() -> None:
    role = _runtime_app_role()
    schema = _schema_name()
    if not role or schema is None or not _role_exists(role):
        return
    role_ident = _quote_ident(role)
    schema_ident = _quote_ident(schema)
    op.execute(f"GRANT USAGE ON SCHEMA {schema_ident} TO {role_ident}")
    op.execute(f"GRANT {TABLE_PRIVILEGES} ON ALL TABLES IN SCHEMA {schema_ident} TO {role_ident}")
    op.execute(f"GRANT {SEQUENCE_PRIVILEGES} ON ALL SEQUENCES IN SCHEMA {schema_ident} TO {role_ident}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema_ident} GRANT {TABLE_PRIVILEGES} ON TABLES TO {role_ident}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema_ident} GRANT {SEQUENCE_PRIVILEGES} ON SEQUENCES TO {role_ident}"
    )


def downgrade() -> None:
    role = _runtime_app_role()
    schema = _schema_name()
    if not role or schema is None or not _role_exists(role):
        return
    role_ident = _quote_ident(role)
    schema_ident = _quote_ident(schema)
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema_ident} REVOKE {SEQUENCE_PRIVILEGES} ON SEQUENCES FROM {role_ident}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema_ident} REVOKE {TABLE_PRIVILEGES} ON TABLES FROM {role_ident}"
    )
    op.execute(f"REVOKE {SEQUENCE_PRIVILEGES} ON ALL SEQUENCES IN SCHEMA {schema_ident} FROM {role_ident}")
    op.execute(f"REVOKE {TABLE_PRIVILEGES} ON ALL TABLES IN SCHEMA {schema_ident} FROM {role_ident}")
    op.execute(f"REVOKE USAGE ON SCHEMA {schema_ident} FROM {role_ident}")
