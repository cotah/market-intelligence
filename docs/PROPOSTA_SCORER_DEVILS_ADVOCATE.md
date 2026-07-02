# Proposta — Fazer o Scorer/status considerar o Devil's Advocate

> Status: **PROPOSTA — nada foi implementado.** Aguardando decisão do Henrique.
> Data: 2026-07-02

## 1. O problema observado

Relatório real (Vertical AI SaaS, 26/06/2026):

- Scorer: **7.0/10 → "Aprovado"**
- Devil's Advocate: *"Worth pursuing only with a painfully narrow vertical...
  as a generic idea, it is too vague and likely to die"* → **reprovou**

O agente mais cético do sistema reprovou e isso não afetou nem a nota nem o status.

## 2. Diagnóstico (confirmado no código)

Os dois agentes rodam **isolados**, e é estrutural — não é um bug pontual:

1. **Ordem da cadeia** (`backend/core/pipeline.py:50-60`): o Scorer é o agente 8
   e o Devil's Advocate é o 10. O Scorer roda **antes** — é impossível ele usar
   o output do DA como input.
2. **Contexto do Scorer** (`backend/agents/scorer.py:_context_block`): monta o
   prompt só com problem/competitors/market/ai/compatibility/monetization.
   Não há campo do DA (nem poderia — ainda não existe quando o Scorer roda).
3. **DA é informativo por design** (`backend/agents/devils_advocate.py:5`):
   "Nao descarta (informa, evita paixao cega)". O output dele
   (`risks[]` com severity, `fatal_flaws[]`, `verdict`) não alimenta nota,
   status nem descarte. Vai direto para o banco e para o relatório.

Isso segue o README (o DA "evita que o fundador se apaixone", mas não decide).
Ou seja: comportamento planejado, com a lacuna que você notou.

## 3. Opções de correção

### Opção A — Selo "Aprovado com ressalvas" (recomendada)

Depois que o DA roda, a pipeline aplica uma regra determinística (em Python,
sem LLM):

```
se len(fatal_flaws) >= 2  OU  qtde de risks com severity == "high" >= 3:
    score_data["risk_flag"] = "high"
    (relatório/frontend mostram "Aprovado com ressalvas" em vez de "Aprovado")
```

- **Não mexe na nota** — score_total continua comparável com o histórico.
- Onde tocar: `core/pipeline.py` (pós-DA), frontend (badge), testes.
- Risco: **baixo**. Dados antigos não têm `risk_flag` → aparecem como hoje.
- Limitação: `fatal_flaws`/`severity` vêm do LLM; a contagem é objetiva, mas o
  conteúdo é subjetivo. Thresholds (2 e 3) ajustáveis via Settings.

### Opção B — Penalidade na nota

Mesma regra da Opção A, mas aplicando desconto no `score_total`
(ex.: −0,5 por fatal flaw, teto de −2,0). Um 7.0 com 2 fatal flaws viraria 6.0;
com 3, cairia para 5.5 → **descartado retroativamente na régua atual**.

- Risco: **médio/alto — breaking change de negócio.**
  - Relatórios antigos teriam nota diferente se reprocessados (7.0 histórico ≠
    7.0 novo). Comparações antes/depois ficam inválidas sem versionar a regra.
  - Interage com dois thresholds: `min_score_to_keep` (6.0) e
    `min_score_for_project_plan` (8.0) — uma penalidade pode descartar ou
    des-gerar plano de ideias que hoje passam.
- Se escolhida: gravar `score_pre_penalty` junto, e marcar a versão da regra
  no `score_data` (ex.: `"scoring_rule": "v2"`).

### Opção C — Mover o DA para antes do Scorer

O Scorer passaria a receber `devils_advocate_data` no `_context_block`.

- Prós: o LLM pondera os riscos "nativamente".
- Contras: muda a ordem canônica do README (DA foi desenhado para criticar a
  ideia **já pontuada** — ele usa `score_data` no próprio prompt,
  `devils_advocate.py:34`). Efeito na nota vira opaco (dentro do LLM), difícil
  de testar e de explicar. **Não recomendo.**

## 4. Recomendação

**Opção A.** Entrega exatamente o que faltou no relatório de 26/06 — o "Aprovado"
deixaria de ser limpo quando o DA reprova — sem tocar em nota, thresholds nem
histórico. Se depois você quiser endurecer, a Opção B pode ser adicionada em
cima, com versionamento da regra.

## 5. Mudança de comportamento esperada (se Opção A for aprovada)

| Cenário | Hoje | Depois |
|---|---|---|
| Score ≥ 6.0, DA tranquilo | Aprovado | Aprovado (igual) |
| Score ≥ 6.0, DA com 2+ fatal flaws ou 3+ riscos high | Aprovado | **Aprovado com ressalvas** |
| Oportunidades antigas (sem `risk_flag`) | — | Aparecem como hoje (sem selo) |
| `score_total` | — | **Inalterado em qualquer cenário** |

Nada é descartado a mais, nenhuma nota muda, nenhuma migração de banco é
necessária (o flag entra no JSONB `score_data` existente).
