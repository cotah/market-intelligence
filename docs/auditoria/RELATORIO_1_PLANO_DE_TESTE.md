# RELATÓRIO 1 — Plano de Teste (Auditoria 05/07/2026)

## Resumo do projeto
Market Intelligence AI — pipeline de 11 agentes (FastAPI + Celery + Redis + PostgreSQL,
deploy Railway; frontend Next.js 15 na Vercel). Caça oportunidades de negócio, filtra pelo
perfil do fundador e pontua 0–10 (≥6 mantém, ≥8 gera plano de projeto).

## Ambiente detectado
- Backend: uv + FastAPI + SQLAlchemy 2.0 async + Alembic (4 migrations, consistentes com models)
- Frontend: npm + Next 15.1.6 + React 19 + TS 5.7 strict + Tailwind 4
- Serviços: Postgres 16 (5434) + Redis 7 (6380) via docker-compose
- Deploy: Dockerfile + Procfile (web/worker/beat) + railway.toml

## Escopo e estratégia
| Área | Estratégia | Prioridade |
|---|---|---|
| Suíte pytest (64 testes) | regressão base | P0 |
| Limpeza SmartTap (ordem explícita) | grep antes/depois + testes | P0 |
| Contrato n8n `/integrations/research/*` | testes existentes + revisão — NÃO QUEBRAR | P0 |
| Contrato frontend↔backend | tsc --noEmit + next build + comparação de tipos | P0 |
| Pipeline (DISCARDED/PARTIAL/COMPLETED, risk_flag, skip <8) | testes existentes | P1 |
| LLM fallback / JSON repair | testes existentes | P1 |
| Integrações externas | mock only (sem gastar créditos) | P2 |
| Celery/Redis/concorrência | análise estática | P2 |
| Produção Railway | somente leitura (GET) | P2 |

## Critérios pass/fail
- Aprovado: pytest 100%, tsc/build limpos, zero "smarttap", contrato n8n intacto,
  comportamentos protegidos preservados (marcador "sem dados" do ProjectGenerator,
  isolamento Scorer/Devil's Advocate).
- Reprovado: teste quebrado sem correção, contrato alterado sem aviso, mudança
  silenciosa de comportamento.

## Áreas críticas identificadas na varredura
1. SmartTap hardcoded (código + README + blueprint) e no banco de produção (seed antigo).
2. Endpoints de controle sem auth (`/pipeline/*`, PUT `/founder-profile`).
3. Fetch do frontend sem timeout.
4. `failed_agents` não exibido no frontend (status PARTIAL sem detalhe).
5. Celery sem `task_time_limit`.
6. Degradação graciosa silenciosa (Serper falha → "zero concorrentes" falso).
7. Sem rate limit no endpoint n8n.
