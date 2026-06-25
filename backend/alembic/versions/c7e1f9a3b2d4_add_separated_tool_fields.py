"""add separated tool fields to founder_profile

Separa o antigo tools_available em ai_tools / software_tools / hardware_tools.
Migracao aditiva: nao remove a coluna legada tools_available.

Revision ID: c7e1f9a3b2d4
Revises: 552fc109d89d
Create Date: 2026-06-25 22:10:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c7e1f9a3b2d4'
down_revision: str | None = '552fc109d89d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# server_default garante que a linha existente (perfil id=1) receba [].
_EMPTY = sa.text("'[]'::jsonb")


def upgrade() -> None:
    op.add_column(
        'founder_profile',
        sa.Column('ai_tools', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=_EMPTY),
    )
    op.add_column(
        'founder_profile',
        sa.Column('software_tools', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=_EMPTY),
    )
    op.add_column(
        'founder_profile',
        sa.Column('hardware_tools', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=_EMPTY),
    )


def downgrade() -> None:
    op.drop_column('founder_profile', 'hardware_tools')
    op.drop_column('founder_profile', 'software_tools')
    op.drop_column('founder_profile', 'ai_tools')
