# Agente de Marketing Analytics — CAPIVAREX

**Data:** 08/07/2026
**Workflow n8n:** `Capivarex — Marketing Analytics Agent` (id `vAalfLSK1xcvQEDA`) — **publicado e ativo**
**Status:** ✅ Construído, testado ao vivo, com persona **VECTOR** aplicada (+ guard de honestidade) e no ar.

> **Resumo "newb":** esse é o agente que **mede** o marketing. Ele junta as vendas (do ATLAS), as interações sociais (da AURA) e os planos (da ORION) de um período, e o Claude transforma tudo num relatório claro: placar de métricas, o que funcionou, o que não, recomendações (escalar/cortar/testar) e alertas. Fecha o ciclo: **criar → medir → melhorar.**

---

## O que ele faz (fluxo)
1. **Recebe** o pedido (produto opcional + período em dias).
2. **Lê o Cérebro:** `financial_ledger` (vendas), `social_interactions` (interações), `campaign_plans` (planos).
3. **Agrega** os números (receita por moeda, pedidos, interações por canal, taxa de resposta).
4. **Claude (Sonnet 4.6)** vira relatório + recomendações.
5. **Grava** em `marketing_reports`.

## Como chamar (webhook)
`POST https://n8n-production-db31.up.railway.app/webhook/capivarex-marketing-analytics`
```json
{ "period_days": 30, "product_name": "SmartTap" }
```
- Sem `product_name` = analisa **todos os produtos**. `period_days` padrão = 30.

## O que grava (`marketing_reports`)
- **scorecard** — placar de métricas (receita, pedidos, ticket, interações, taxa de resposta…).
- **wins / misses** — o que funcionou e o que não.
- **recommendations** — ações com prioridade (alta/média/baixa) e justificativa.
- **alerts** — sinais de alerta.
- **summary** — resumo executivo.

## Teste real feito (todos os produtos, 30 dias)
Leu os dados reais (1 venda de $20, 3 interações: 2 Facebook + 1 Instagram, 100% respondidas) e foi **honesto**: "pré-tração, amostra n=1, foco em volume". Ainda **pegou 2 problemas reais**:
- ⚠️ Receita em **USD** numa operação de **Dublin** → verificar moeda de cobrança.
- Recomendou demos presenciais + meta mínima de pedidos como KPI de sobrevivência.

**Nota de calibração:** numa rodada ele disse "3 planos duplicados" quando só há 1 — um exagero de leitura. Será corrigido com um guard no prompt ao aplicar a persona.

## Sinergia (empresa conectada)
Ele usa dados de **3 agentes**: ATLAS (vendas), AURA (interações) e ORION (planos). É o "olho" que fecha o ciclo do marketing e alimenta a ORION e o ATLAS de volta.

## Custo / economia
- 1 chamada Claude (`max_tokens` 1800) + 3 leituras baratas no Supabase. **Não usa Serper.** Prompt telegráfico.

## Segurança / robustez
- Workflow **novo e isolado** — não toca em nada existente.
- Leituras degradam sem quebrar (período sem dados gera relatório de "sem dados" em vez de erro).
- **Rollback:** desativar/arquivar o workflow.

## Persona
- **VECTOR** (Head de Growth & Analytics) aplicada no `system`, com **guard de honestidade** (não inventa números/duplicatas; respeita amostra pequena). Verificado ao vivo.

## Pendente (futuro, opcional)
- Integrar **Meta Ads insights** quando houver campanhas pagas rodando, pra medir CAC/ROAS reais.
- Cache de prompt + agendamento semanal com email (os "turbos" baratos).
