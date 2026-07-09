# Agente Estrategista de Campanha — CAPIVAREX

**Data:** 08/07/2026
**Workflow n8n:** `Capivarex — Campaign Strategist Agent` (id `ar4wWQV0JQwqgmnJ`) — **publicado e ativo**
**Status:** ✅ Construído, testado ao vivo (SmartTap) e gravando no Cérebro.

> **Resumo "newb":** esse é o "maestro" do marketing. Você diz o objetivo (lançar, promover, captar leads) e ele monta o plano de campanha **completo — online E offline** (anúncios, redes, porta a porta, flyers), com posicionamento, calendário, divisão do orçamento, metas (KPIs) e **as tarefas de cada agente-peça** (Copy, Creative, Ads, Social, Email, Vídeo). Ele puxa sozinho a **marca** do produto e a **inteligência da PIA** pra deixar o plano afiado.

---

## O que ele faz (fluxo)
1. **Recebe** o pedido (objetivo + produto + orçamento + prazo + público).
2. **Lê o Cérebro:** `brand_context` (marca/tom/preço) + `competitive_intel` (última análise da PIA).
3. **Claude (Sonnet 4.6)** monta o plano de campanha completo.
4. **Grava** em `campaign_plans`.
5. **Retorna** o plano em JSON.

## Como chamar (webhook)
`POST https://n8n-production-db31.up.railway.app/webhook/capivarex-campaign-strategist`
```json
{
  "product_name": "SmartTap",
  "objective": "lancamento",
  "budget": "500 euros",
  "duration": "30 dias",
  "audience": "pequenos negócios locais em Dublin"
}
```
- `product_name` é o único obrigatório. `objective` pode ser lançamento, promoção, lead, awareness.

## O que ele devolve / grava (`campaign_plans`)
- **positioning** — posicionamento em 1 frase.
- **channels** — até 4 canais (online + offline) com tática e mensagem.
- **content_calendar** — fases (ex: pré-lançamento, lançamento, aceleração) com ações.
- **budget_split** — divisão do orçamento em %.
- **kpis** — metas mensuráveis.
- **agent_tasks** — o que cada agente-peça faz (Copy, Creative, Ads, Social, Email, Vídeo). ← ponte pra orquestração (Fase 4).
- **summary** — resumo em 1 frase.

## Teste real feito (SmartTap, €500, 30 dias, Dublin)
Rodou de ponta a ponta e usou a inteligência da PIA. Exemplos:
- **Canais:** Google Ads (search local), Instagram/Meta (vídeo demo), **porta a porta em Ranelagh/Rathmines/Temple Bar**, outreach em grupos.
- **Orçamento:** 40% Google, 30% Meta, 20% offline (flyers/NFC), 10% ferramentas.
- **Tarefas:** Copy → 3 variações de anúncio; Creative → flyer A5 com QR; Ads → campanha Meta segmentada; Social → 6 posts; Email → sequência de 3; Vídeo → demo de 30s do toque gerando review.

## Sinergia com a PIA
Ele **lê a última análise da PIA** do produto e usa nas mensagens (ex: "Birdeye cobra €497, SmartTap entrega o essencial por €39"). Rode a PIA antes pra deixar a campanha ainda mais afiada.

## Custo / economia
- 1 chamada Claude (`max_tokens` 3000, teto) + 2 leituras baratas no Supabase. **Não usa Serper.**
- Prompt **telegráfico** (campos curtos) pra não desperdiçar token.

## Segurança / robustez
- Workflow **novo e isolado** — não toca em nenhum agente existente.
- As leituras do Cérebro degradam sem quebrar (produto sem marca/intel ainda gera plano).
- **v1 só gera o plano** — não aciona os agentes-peça ainda (isso é a Fase 4, orquestração).
- **Rollback:** desativar/arquivar o workflow.

## Próximo (opcional)
- Dar um **nome/persona** a ele (como PIA, AURA, NEXA, ATLAS).
- Na Fase 4, o CEO usa o `agent_tasks` pra **acionar** Copy/Creative/Ads/Social/Email/Vídeo automaticamente.
