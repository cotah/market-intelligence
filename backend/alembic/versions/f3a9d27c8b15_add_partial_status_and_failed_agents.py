"""add PARTIAL status and failed_agents column

Um topico que termina a cadeia com algum agente falho vira PARTIAL (em vez
de COMPLETED) e registra quem falhou em failed_agents. Assim uma oportunidade
"completa" nunca esconde dado faltando.

Revision ID: f3a9d27c8b15
Revises: c7e1f9a3b2d4
Create Date: 2026-07-02
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f3a9d27c8b15'
down_revision: str | None = 'c7e1f9a3b2d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ADD VALUE e seguro em producao (nao trava a tabela). Postgres 12+
    # permite dentro de transacao desde que o valor nao seja usado nela.
    op.execute("ALTER TYPE opportunity_status ADD VALUE IF NOT EXISTS 'PARTIAL'")
    op.add_column(
        'opportunities',
        sa.Column('failed_agents', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('opportunities', 'failed_agents')
    # Postgres nao suporta remover um valor de enum; 'PARTIAL' fica no tipo
    # (inofensivo — nenhuma linha nova o usara apos o downgrade do codigo).
