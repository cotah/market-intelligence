# RELATÓRIO 2 — Resultados da Auditoria (05/07/2026)

## 1. O que foi testado
- **Backend:** suíte completa (7 arquivos, 64 testes) — pipeline, agentes, LLM fallback/JSON repair,
  founder profile (seed/load/save), Research API n8n (auth 401/403/503, mock, paging), summarize.
- **Frontend:** `tsc --noEmit` (strict) e `next build` de produção.
- **Repo inteiro:** grep case-insensitive por "smarttap" (incluindo arquivos ignorados pelo git).
- **Produção (somente leitura):** GET /health e GET /founder-profile no Railway.

## 2. Resultados
| Checagem | Resultado |
|---|---|
| pytest (antes das mudanças) | ✅ 64/64 |
| pytest (depois das mudanças) | ✅ 64/64 |
| tsc --noEmit | ✅ limpo |
| next build | ✅ exit 0 |
| grep smarttap (depois) | ✅ zero ocorrências |
| Contrato n8n | ✅ intacto (nenhum arquivo de API tocado) |

## 3. O que foi corrigido
**Issue #1 — Resíduo "SmartTap" hardcoded (Major, ordem explícita do fundador).**
12 ocorrências removidas/generalizadas, correção mínima, sem mudança de lógica:
- `backend/core/founder_profile.py:24` — `active_projects` agora `["TALOA", "InMyHouses"]`
- `README.md:200` — idem (doc sincronizada com o código)
- `docs/CAPIVAREX_AI_COMPANY_BLUEPRINT.md` — 10 menções substituídas por "produto piloto" /
  "outro produto" / "landing_produto", preservando o sentido histórico do documento.

Risco de regressão: baixíssimo (dados de perfil/docs; nenhum agente trata SmartTap
de forma especial). Validado com suíte completa verde após a mudança.

## 4. Pendências (requerem decisão/confirmação do Henrique)
1. **[Major] Banco de PRODUÇÃO ainda contém SmartTap** — GET /founder-profile retorna
   `active_projects: "SmartTap, TALOA, InMyHouses"`. O perfil do banco (editado via UI) tem
   precedência sobre o hardcode e alimenta os prompts dos agentes. Correção: editar o campo
   na página /profile do frontend (ou PUT /founder-profile). NÃO alterado nesta auditoria —
   escrita em produção só com confirmação.
2. **[Major] Railway com `environment: development`** — /health de produção reporta
   "development". Efeitos: logs em modo console (não JSON). Verificar também ALLOWED_ORIGINS.
   Correção: setar `ENVIRONMENT=production` no Railway.
3. **[Major] Endpoints de controle sem auth** — /pipeline/start|stop|run-once e
   PUT /founder-profile são públicos: qualquer pessoa com a URL pode ligar a pipeline
   (gasta créditos de LLM) ou alterar o perfil. Proposta: API key simples validada por
   header (mesmo padrão da Research API), com o frontend enviando a chave. Muda contrato
   frontend↔backend → não aplicado sem aprovação.
4. **[Minor] Fetch do frontend sem timeout** (`src/lib/api.ts`) — UI pode pendurar se o
   backend cair. Correção sugerida: AbortController com ~15s.
5. **[Minor] `failed_agents` não exibido** — status PARTIAL aparece no frontend, mas sem
   detalhe de quais agentes falharam (o dado já vem na API).
6. **[Minor] Celery sem `task_time_limit`** — task pode rodar indefinidamente.
7. **[Minor] Degradação silenciosa** — integração externa que falha vira "sem dados" para o
   agente seguinte (ex.: Serper fora → "zero concorrentes"). Sugerido marcar a origem da falha.
8. **[Minor] Sem rate limit** no endpoint n8n.

## 5. Limitações do ambiente
- App não foi executado end-to-end localmente (exigiria Docker + chaves de LLM reais e
  gastaria créditos). Testes existentes são isolados (sem BD/Redis reais) e cobrem a lógica.
- Celery/Redis/concorrência validados por análise estática, não em runtime.
- Como validar depois: `docker compose up -d` + `cd backend && uv run alembic upgrade head`
  + `uv run uvicorn main:app` + `uv run celery -A celery_app worker` e rodar POST /pipeline/run-once.

## 6. Métricas
- Bugs/resíduos encontrados: 9 (1 corrigido, 8 documentados como pendência com proposta)
- Ocorrências SmartTap removidas: 12 (3 arquivos)
- Testes: 64 antes → 64 depois (0 regressões); nenhum teste novo necessário (mudança de dados, não lógica)
- Arquivos alterados: 3 + 2 relatórios novos em docs/auditoria/

## 7. Veredito
**Sistema estável.** Suíte verde, builds limpos, contrato n8n intacto, comportamentos
protegidos preservados. Nada bloqueia o uso atual. Antes de exposição pública maior,
priorizar: perfil de produção (item 1), ENVIRONMENT no Railway (item 2) e auth nos
endpoints de controle (item 3).
