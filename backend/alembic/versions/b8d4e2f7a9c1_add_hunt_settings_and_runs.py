"""hunt: settings por conta + registro de uso das rodadas

- hunt_settings: 1 linha por conta (PK = account_id) com enabled (default
  false = opt-in), frequency (manual|daily|weekly|monthly), topic e os
  timestamps last_run_at/next_run_at usados pelo scheduler do Beat.
- hunt_runs: registro de uso de cada rodada (base do debito de Caps na
  Fase 2). Indice composto para leitura por conta.

Revision ID: b8d4e2f7a9c1
Revises: a1b2c3d4e5f6
Create Date: 2026-07-18
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b8d4e2f7a9c1'
down_revision: str | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hunt_settings",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "frequency", sa.String(length=20), nullable=False, server_default="manual"
        ),
        sa.Column("topic", sa.Text(), nullable=False, server_default=""),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # O scheduler varre "quem esta na hora": enabled + next_run_at <= agora.
    op.create_index(
        "ix_hunt_settings_enabled_next_run",
        "hunt_settings",
        ["enabled", "next_run_at"],
    )

    op.create_table(
        "hunt_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("topic", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "trigger", sa.String(length=20), nullable=False, server_default="manual"
        ),
        sa.Column(
            "status",
            sa.Enum("RUNNING", "COMPLETED", "FAILED", name="hunt_run_status"),
            nullable=False,
            server_default="RUNNING",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_hunt_runs_account_started", "hunt_runs", ["account_id", "started_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_hunt_runs_account_started", table_name="hunt_runs")
    op.drop_table("hunt_runs")
    sa.Enum(name="hunt_run_status").drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_hunt_settings_enabled_next_run", table_name="hunt_settings")
    op.drop_table("hunt_settings")
