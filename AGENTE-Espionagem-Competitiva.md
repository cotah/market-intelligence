# Agente de Espionagem Competitiva — CAPIVAREX

**Data:** 08/07/2026
**Workflow n8n:** `Capivarex — Competitive Intel Agent` (id `djWRFOGqGl18jqRJ`) — **publicado e ativo**
**Status:** ✅ Construído, testado ao vivo (SmartTap) e gravando no Cérebro.

> **Resumo "newb":** esse agente vigia os concorrentes de um produto seu e "rouba" o que é bom: quais funcionalidades copiar, onde eles são fracos (suas oportunidades), alertas de preço e ideias novas. Ele pesquisa na internet (Perplexity, com fontes), o Claude organiza num plano de ação, e tudo fica salvo no Cérebro (Supabase) pro Produto e o Marketing usarem.

---

## O que ele faz (fluxo)

1. **Recebe** um pedido (produto + concorrentes opcionais).
2. **Pesquisa** os concorrentes na internet via **Perplexity `sonar`** (com fontes/citações).
3. **Claude (Sonnet 4.6)** transforma a pesquisa num **plano acionável**.
4. **Grava** o resultado no Cérebro, na tabela `competitive_intel`.
5. **Retorna** o resultado em JSON.

## Como chamar (webhook)

`POST https://n8n-production-db31.up.railway.app/webhook/capivarex-competitive-intel`

Corpo (JSON):
```json
{
  "product_name": "SmartTap",
  "category": "cartões/adesivos NFC para avaliações no Google e fidelidade de pequenos negócios",
  "location": "Dublin, Ireland",
  "competitors": "Tapmango, Popl, Birdeye",
  "our_product_summary": "SmartTap é um cartão/adesivo NFC ... um toque, sem app."
}
```
- `product_name` é o único obrigatório. Se `competitors` ficar vazio, o agente **descobre** os principais sozinho.

## O que ele devolve / grava (tabela `competitive_intel`)
- **competitors** — cada concorrente com posicionamento, funcionalidades, preço, forças, fraquezas e reclamações dos clientes.
- **features_to_steal** — funcionalidades a copiar (com o porquê e o esforço low/medium/high).
- **gaps_to_exploit** — onde os concorrentes falham (suas oportunidades).
- **pricing_alerts** — inteligência de preço.
- **product_ideas** — ideias novas.
- **summary** — resumo em 1-2 frases.
- **raw** — a pesquisa bruta (auditoria).

## Teste real feito (SmartTap)
Rodou de ponta a ponta. Exemplos do que ele trouxe:
- **Copiar:** automação de SMS pós-toque; integração com CRM; dashboard de avaliações; fidelidade configurável.
- **Explorar (gaps):** único NFC físico que une avaliação Google + fidelidade + Instagram sem app; preço transparente onde Birdeye/TapMango falham; simplicidade radical para negócios de 1-5 pessoas.
- **Preço:** ficar abaixo de $35/mês (Popl); publicar preço fixo; evitar cobrança por localização.

## Custo / economia
- Usa **Perplexity `sonar`** (barato) — o teste completo custou **~$0,006**. **Não usa Serper.**
- `max_tokens` limitado (Perplexity 1400 / Claude 1800) e prompts concisos para não desperdiçar token.

## Segurança / robustez
- Workflow **novo e isolado** — não toca em nenhum agente existente.
- Credenciais reaproveitadas (Perplexity, Anthropic, Supabase) — nenhum segredo no código.
- Se o parse do JSON falhar, degrada sem quebrar (guarda o texto bruto).
- **Rollback:** desativar/arquivar o workflow — zero impacto no resto.

## Próximo (opcional)
- Agendar rodadas automáticas (ex: semanal por produto) — via tarefa agendada.
- Ligar no CEO/orquestração (Fase 4) para o Produto receber as ideias automaticamente.
