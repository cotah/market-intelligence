"""Multi-tenancy: identificacao da conta dona de cada dado.

Cada cliente tem um `account_id` (UUID). Todo endpoint exige o header
X-Account-Id (mesmo padrao do frontend): sem header ou com valor invalido
=> 400. NUNCA devolvemos dado "global" como fallback — e isso que impede
um cliente de enxergar dados de outro.

A conta do dono (workspace do Henrique) e o UUID fixo abaixo; as linhas
antigas do banco foram backfilladas para ela na migration.
"""

import uuid

from fastapi import Header, HTTPException

from core.logging_config import get_logger

log = get_logger("tenancy")

# Workspace do dono. Tambem e o server_default das colunas account_id
# (backfill das linhas pre-multi-tenant).
OWNER_ACCOUNT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def require_account_id(
    x_account_id: str | None = Header(default=None, alias="X-Account-Id"),
) -> uuid.UUID:
    """Dependency FastAPI: extrai e valida o account_id do header.

    Regra de ouro: sem X-Account-Id (ou com valor que nao e UUID) => 400.
    Nunca assumimos uma conta padrao aqui — fallback silencioso e vazamento.
    """
    if not x_account_id:
        log.warning("tenancy.missing_account_id")
        raise HTTPException(status_code=400, detail="Missing X-Account-Id header")
    try:
        return uuid.UUID(x_account_id.strip())
    except ValueError:
        log.warning("tenancy.invalid_account_id")
        raise HTTPException(
            status_code=400, detail="Invalid X-Account-Id header (must be a UUID)"
        ) from None
