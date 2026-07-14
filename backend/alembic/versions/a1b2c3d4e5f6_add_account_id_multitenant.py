"""multi-tenant: account_id em opportunities, daily_reports e founder_profile

- opportunities/daily_reports: account_id UUID NOT NULL com server_default =
  workspace do dono (backfill automatico das linhas existentes) + indices
  compostos para as leituras filtradas por conta.
- founder_profile: deixa de ser singleton (id=1) e passa a ter 1 linha por
  conta (PK = account_id). A linha existente vira o perfil do dono.

Revision ID: a1b2c3d4e5f6
Revises: f3a9d27c8b15
Create Date: 2026-07-14
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = 'f3a9d27c8b15'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Workspace do dono (core/tenancy.py: OWNER_ACCOUNT_ID).
OWNER = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # --- opportunities / daily_reports: coluna + backfill via default ---
    op.add_column(
        "opportunities",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text(f"'{OWNER}'"),
        ),
    )
    op.add_column(
        "daily_reports",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text(f"'{OWNER}'"),
        ),
    )
    op.create_index(
        "ix_opportunities_account_created", "opportunities", ["account_id", "created_at"]
    )
    op.create_index(
        "ix_opportunities_account_score", "opportunities", ["account_id", "score_total"]
    )
    op.create_index(
        "ix_daily_reports_account_date", "daily_reports", ["account_id", "report_date"]
    )

    # --- founder_profile: singleton (id=1) -> 1 linha por conta ---
    op.add_column(
        "founder_profile",
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text(f"'{OWNER}'"),
        ),
    )
    op.drop_constraint("founder_profile_pkey", "founder_profile", type_="primary")
    op.create_primary_key("founder_profile_pkey", "founder_profile", ["account_id"])
    op.drop_column("founder_profile", "id")


def downgrade() -> None:
    # founder_profile: volta ao singleton — mantem SO a linha do dono (id=1).
    op.execute(f"DELETE FROM founder_profile WHERE account_id != '{OWNER}'")
    op.add_column(
        "founder_profile",
        sa.Column("id", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.drop_constraint("founder_profile_pkey", "founder_profile", type_="primary")
    op.create_primary_key("founder_profile_pkey", "founder_profile", ["id"])
    op.drop_column("founder_profile", "account_id")

    op.drop_index("ix_daily_reports_account_date", table_name="daily_reports")
    op.drop_index("ix_opportunities_account_score", table_name="opportunities")
    op.drop_index("ix_opportunities_account_created", table_name="opportunities")
    op.drop_column("daily_reports", "account_id")
    op.drop_column("opportunities", "account_id")
