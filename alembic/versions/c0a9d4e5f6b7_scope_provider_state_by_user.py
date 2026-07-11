"""scope provider state by user

Revision ID: c0a9d4e5f6b7
Revises: bd25b66f82e8
Create Date: 2026-07-09 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c0a9d4e5f6b7"
down_revision: str | Sequence[str] | None = "bd25b66f82e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_USER_ID = "default"


def _recreate_system_setting_for_upgrade() -> None:
    op.create_table(
        "system_setting_user_scoped",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(), server_default=DEFAULT_USER_ID, nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key", name="uq_system_setting_user_key"),
    )
    op.execute(
        sa.text(
            "INSERT INTO system_setting_user_scoped (id, user_id, key, value, updated_at) "
            "SELECT id, :user_id, key, value, updated_at FROM system_setting"
        ).bindparams(user_id=DEFAULT_USER_ID)
    )
    op.drop_table("system_setting")
    op.rename_table("system_setting_user_scoped", "system_setting")
    op.create_index("ix_system_setting_user_id", "system_setting", ["user_id"], unique=False)


def _recreate_system_setting_for_downgrade() -> None:
    op.create_table(
        "system_setting_global",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_system_setting_key"),
    )
    op.execute(
        sa.text(
            "INSERT INTO system_setting_global (id, key, value, updated_at) "
            "SELECT id, key, value, updated_at FROM system_setting WHERE user_id = :user_id"
        ).bindparams(user_id=DEFAULT_USER_ID)
    )
    op.drop_table("system_setting")
    op.rename_table("system_setting_global", "system_setting")


def upgrade() -> None:
    _recreate_system_setting_for_upgrade()

    with op.batch_alter_table("provider_config", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(), server_default=DEFAULT_USER_ID, nullable=False))
        batch_op.create_foreign_key("fk_provider_config_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE")
        batch_op.drop_constraint("uq_provider_key", type_="unique")
        batch_op.create_unique_constraint(
            "uq_provider_config_user_provider_key",
            ["user_id", "provider", "key"],
        )
        batch_op.create_index("ix_provider_config_user_id", ["user_id"], unique=False)
        batch_op.create_index("ix_provider_config_user_provider", ["user_id", "provider"], unique=False)

    with op.batch_alter_table("provider_credential", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(), server_default=DEFAULT_USER_ID, nullable=False))
        batch_op.create_foreign_key("fk_provider_credential_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE")
        batch_op.drop_index("uq_provider_credential_one_active")
        batch_op.create_index("ix_provider_credential_user_id", ["user_id"], unique=False)
        batch_op.create_index("ix_provider_credential_user_provider", ["user_id", "provider"], unique=False)
        batch_op.create_index(
            "uq_provider_credential_one_active",
            ["user_id", "provider"],
            unique=True,
            postgresql_where=sa.text("is_active"),
        )

    with op.batch_alter_table("custom_provider", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(), server_default=DEFAULT_USER_ID, nullable=False))
        batch_op.create_foreign_key("fk_custom_provider_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE")
        batch_op.create_index("ix_custom_provider_user_id", ["user_id"], unique=False)


def downgrade() -> None:
    _recreate_system_setting_for_downgrade()

    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM provider_config WHERE user_id <> :user_id").bindparams(user_id=DEFAULT_USER_ID))
    bind.execute(
        sa.text("DELETE FROM provider_credential WHERE user_id <> :user_id").bindparams(user_id=DEFAULT_USER_ID)
    )
    bind.execute(sa.text("DELETE FROM custom_provider WHERE user_id <> :user_id").bindparams(user_id=DEFAULT_USER_ID))

    with op.batch_alter_table("custom_provider", schema=None) as batch_op:
        batch_op.drop_index("ix_custom_provider_user_id")
        batch_op.drop_constraint("fk_custom_provider_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("provider_credential", schema=None) as batch_op:
        batch_op.drop_index("uq_provider_credential_one_active")
        batch_op.drop_index("ix_provider_credential_user_provider")
        batch_op.drop_index("ix_provider_credential_user_id")
        batch_op.drop_constraint("fk_provider_credential_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")
        batch_op.create_index(
            "uq_provider_credential_one_active",
            ["provider"],
            unique=True,
            postgresql_where=sa.text("is_active"),
        )

    with op.batch_alter_table("provider_config", schema=None) as batch_op:
        batch_op.drop_index("ix_provider_config_user_provider")
        batch_op.drop_index("ix_provider_config_user_id")
        batch_op.drop_constraint("uq_provider_config_user_provider_key", type_="unique")
        batch_op.drop_constraint("fk_provider_config_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")
        batch_op.create_unique_constraint("uq_provider_key", ["provider", "key"])
