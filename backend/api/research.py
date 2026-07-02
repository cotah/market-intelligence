"""Ponte Research Agent (n8n) -> busca.

O n8n CONSULTA oportunidades ja filtradas pelos 11 agentes (somente leitura,
portanto idempotente por natureza: retries nunca duplicam nem corrompem dados).

Seguranca:
- Chave DEDICADA via env RESEARCH_API_KEY (header X-API-Key), comparada com
  secrets.compare_digest (timing-safe). Sem chave configurada => 503 (fail
  closed). A chave NUNCA aparece em logs.

Modo mock: ?mock=true devolve payload simulado realista sem tocar no banco,
para testar o fluxo no n8n sem custo.

Contrato de status: 200 ok | 401 sem chave | 403 chave errada | 404 nao
encontrado | 422 invalido | 500 erro real (nunca mascarado como sucesso).

Guia do consumidor (timeout/retry recomendados): docs/INTEGRACAO_N8N_RESEARCH.md
"""

import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import OpportunityOut, ResearchOpportunitiesOut
from core.config import settings
from core.database import get_session
from core.logging_config import get_logger
from models import Opportunity, OpportunityStatus

log = get_logger("api.research")

router = APIRouter(prefix="/integrations/research", tags=["research-bridge"])

# auto_error=False para controlarmos os codigos (401 vs 403) manualmente.
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_research_key(api_key: str | None = Security(_api_key_header)) -> None:
    """Valida a chave dedicada da ponte. Nunca loga o valor recebido."""
    if not settings.research_api_key:
        # Fail closed: sem chave configurada no ambiente, endpoint desligado.
        log.warning("research.auth.not_configured")
        raise HTTPException(status_code=503, detail="Research bridge not configured")
    if not api_key:
        log.warning("research.auth.missing_key")
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if not secrets.compare_digest(api_key, settings.research_api_key):
        log.warning("research.auth.invalid_key")
        raise HTTPException(status_code=403, detail="Invalid API key")


def _mock_opportunities() -> list[OpportunityOut]:
    """Amostra realista com a MESMA estrutura que os agentes produzem."""
    now = datetime(2026, 6, 26, 12, 0, 0)
    return [
        OpportunityOut(
            id=uuid.UUID("00000000-0000-4000-8000-000000000001"),
            title="[MOCK] Vertical AI SaaS",
            summary="Resposta simulada para testes de integracao (mock=true).",
            topic_origin="Vertical AI SaaS",
            source="trend_hunter",
            status=OpportunityStatus.COMPLETED,
            discard_reason=None,
            discarded_by=None,
            failed_agents=None,
            trend_data={"name": "Vertical AI SaaS", "growth_signal": "high"},
            problem_data={"pain_phrases": ["I hate generic AI tools"], "has_real_pain": True},
            competitor_data={"saturation": "medium", "gaps": ["no vertical focus"]},
            market_data={"tam": "$12B", "som": "$3M", "growth_rate": "22%/yr"},
            ai_opportunity_data={"verdict": "YES", "ai_role": "core"},
            compatibility_data={"score": 78, "time_to_mvp": "2 months"},
            monetization_data={"recommended": ["subscription", "api"]},
            score_data={"total": 7.0, "market": 8, "competition": 6, "reasoning": "mock"},
            project_plan={
                "skipped": True,
                "score": 7.0,
                "min_required": 8.0,
                "reason": "Score 7.0 abaixo do minimo 8.0 — plano nao gerado (comportamento esperado).",
            },
            devils_advocate_data={
                "risks": [{"risk": "incumbents", "severity": "high"}],
                "fatal_flaws": ["too generic without a narrow vertical"],
                "why_nobody_buys": "generic positioning",
                "verdict": "worth pursuing only with a painfully narrow vertical",
            },
            score_total=7.0,
            created_at=now,
            updated_at=now,
        )
    ]


@router.get("/opportunities", response_model=ResearchOpportunitiesOut)
async def research_list_opportunities(
    _: None = Depends(require_research_key),
    session: AsyncSession = Depends(get_session),
    score_min: float | None = Query(default=None, ge=0, le=10),
    status: OpportunityStatus | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    mock: bool = Query(default=False),
) -> ResearchOpportunitiesOut:
    """Lista oportunidades ja analisadas, ordenadas por score (desc).

    Somente leitura => chamadas repetidas (retry do n8n) sao seguras.
    """
    if mock:
        items = _mock_opportunities()
        log.info("research.list.mock", count=len(items))
        return ResearchOpportunitiesOut(count=len(items), mock=True, opportunities=items)

    stmt = select(Opportunity)
    if score_min is not None:
        stmt = stmt.where(Opportunity.score_total >= score_min)
    if status is not None:
        stmt = stmt.where(Opportunity.status == status)
    stmt = (
        stmt.order_by(desc(Opportunity.score_total).nulls_last(), desc(Opportunity.created_at))
        .limit(limit)
    )

    result = await session.execute(stmt)
    opps = list(result.scalars().all())

    # Log rastreavel: filtros e volume, nunca chave/PII.
    log.info(
        "research.list.completed",
        count=len(opps),
        score_min=score_min,
        status=status.value if status else None,
        limit=limit,
    )
    items = [OpportunityOut.model_validate(o) for o in opps]
    return ResearchOpportunitiesOut(count=len(items), mock=False, opportunities=items)


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityOut)
async def research_get_opportunity(
    opportunity_id: uuid.UUID,
    _: None = Depends(require_research_key),
    session: AsyncSession = Depends(get_session),
) -> Opportunity:
    """Detalhe completo de uma oportunidade (dados dos 11 agentes)."""
    opp = await session.get(Opportunity, opportunity_id)
    if opp is None:
        log.info("research.get.not_found", opportunity_id=str(opportunity_id))
        raise HTTPException(status_code=404, detail="Opportunity not found")
    log.info("research.get.completed", opportunity_id=str(opportunity_id))
    return opp
