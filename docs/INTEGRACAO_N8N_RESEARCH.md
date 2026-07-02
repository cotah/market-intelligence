# Integração — Research Agent (n8n) → busca

Direção: o n8n **consulta** o busca para puxar oportunidades já filtradas
pelos 11 agentes. Somente leitura — nada é criado/alterado, então retries
nunca duplicam nem corrompem dados (idempotência garantida por design).

## Endpoints

Base (produção Railway): `https://<seu-backend>.up.railway.app`

| Método | Rota | Retorna |
|---|---|---|
| GET | `/integrations/research/opportunities` | Lote de oportunidades (score desc) |
| GET | `/integrations/research/opportunities/{id}` | Detalhe completo (11 agentes) |

### Query params (lista)

- `score_min` (0–10) — ex.: `6` para só promissoras
- `status` — `completed` \| `partial` \| `discarded` \| `in_progress`
- `limit` (1–100, default 20)
- `mock=true` — resposta simulada realista, **sem tocar no banco nem gastar
  API**. Use para montar/testar o fluxo no n8n.

### Autenticação

Header `X-API-Key: <RESEARCH_API_KEY>`.

- Chave **dedicada** — não reaproveita nenhuma outra do projeto.
- Configurar no Railway (Variables) como `RESEARCH_API_KEY`. Gere um valor
  aleatório longo, ex.: `openssl rand -hex 32`. Nunca hardcodar.
- Sem a env configurada, o endpoint responde 503 (fail closed).
- A chave nunca aparece nos logs do backend.

### Status codes

| Código | Significado |
|---|---|
| 200 | Sucesso |
| 401 | Header `X-API-Key` ausente |
| 403 | Chave errada |
| 404 | Oportunidade não encontrada (rota por id) |
| 422 | Parâmetro inválido (ex.: `score_min=15`) |
| 500 | Erro real do servidor (nunca mascarado como sucesso) |
| 503 | Ponte não configurada (env `RESEARCH_API_KEY` vazia) |

## Configuração recomendada no n8n (lado consumidor)

- **Timeout:** 30 s (a consulta é leitura simples; se passar disso, algo
  está errado — não espere mais).
- **Retry:** 3 tentativas com backoff exponencial: 2 s → 4 s → 8 s.
  - Repetir em: timeout, 5xx, 503.
  - **Não repetir** em 401/403/404/422 (repetir não vai mudar o resultado).
- No node HTTP Request: `Retry On Fail = true`, `Max Tries = 3`,
  `Wait Between Tries = 2000` (o n8n não faz backoff exponencial nativo no
  node HTTP; 3×2 s fixo é aceitável para este caso).

## Formato da resposta (lista)

```json
{
  "count": 1,
  "mock": false,
  "opportunities": [
    {
      "id": "…",
      "title": "Vertical AI SaaS",
      "status": "completed",
      "score_total": 7.0,
      "trend_data": { … },
      "problem_data": { … },
      "competitor_data": { … },
      "market_data": { … },
      "ai_opportunity_data": { … },
      "compatibility_data": { … },
      "monetization_data": { … },
      "score_data": { "total": 7.0, … },
      "project_plan": { "skipped": true, "reason": "Score 7.0 abaixo do minimo 8.0 …" },
      "devils_advocate_data": { "risks": […], "fatal_flaws": […], "verdict": "…" },
      "failed_agents": null,
      "created_at": "…", "updated_at": "…"
    }
  ]
}
```

Mesma estrutura que os agentes já produzem (schema `OpportunityOut`) — nada
foi reinventado. Obs.: `project_plan` pode conter o plano completo (score ≥ 8)
ou o marcador `{"skipped": true, …}` (score < 8, comportamento esperado).

## Exemplo de chamada

```bash
curl -H "X-API-Key: $RESEARCH_API_KEY" \
  "https://<backend>/integrations/research/opportunities?score_min=6&status=completed&limit=10"

# Teste sem gastar nada:
curl -H "X-API-Key: $RESEARCH_API_KEY" \
  "https://<backend>/integrations/research/opportunities?mock=true"
```
