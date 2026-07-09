# PLANO — Levar a CAPIVAREX a 100%

**Data:** 08/07/2026
**Situação:** ~85% da empresa pronta. Este documento é o **guia** que vamos seguir para completar os ~15% que faltam **sem quebrar nada**.

> **Resumo "newb":** a gente já tem quase tudo funcionando. Falta construir alguns "funcionários" (agentes) novos e, por último, ligar o "chefe" (CEO) que coordena todo mundo. Este plano coloca isso em ordem: primeiro o que é seguro (peças novas e isoladas), por último o que é delicado (a orquestração). Cada passo tem como testar e como desfazer.

---

## Princípios de segurança (valem para TODAS as fases)

1. **Novo antes de mexer no velho.** Todo agente novo é um workflow **separado**. Não tocamos em nada que já roda.
2. **Testar antes de ligar.** Todo agente roda primeiro em modo rascunho/mock (custo ~zero), depois um teste real pequeno.
3. **Conectar ao Cérebro.** Todo resultado é gravado no Supabase (Cérebro Compartilhado) para os outros usarem.
4. **Rollback trivial.** Como cada agente é isolado, desfazer = desativar o workflow. Zero impacto no resto.
5. **Sem gasto sem porteiro.** Nenhum agente gasta dinheiro real sem passar pelo ATLAS.
6. **Documentar e marcar "pronto"** ao fim de cada agente.

---

## Receita padrão de cada agente novo (o "como", pra não dar erro)

Todo agente segue exatamente estes 8 passos:

1. Definir a **persona** + o **contrato** (o que entra e o que sai, em JSON).
2. Criar o **workflow novo** no n8n (isolado).
3. Ligar as **credenciais que já existem** (Claude, Supabase, Meta, etc.).
4. Testar em **dry-run/mock** (sem gastar, sem publicar).
5. Testar **real** com 1 caso pequeno.
6. Gravar o resultado no **Cérebro** (tabela própria no Supabase).
7. **Validar + publicar**.
8. **Documentar** e marcar como pronto.

---

## A sequência (5 fases, da mais segura para a mais delicada)

### FASE 1 — Fechar o ciclo de Marketing + Espionagem *(3 agentes novos, isolados, alto valor)*

**1.1 — Agente de Espionagem Competitiva**
- **Objetivo:** vigiar os concorrentes dos SEUS produtos e "roubar" o que é bom (features, preços, ângulos de campanha) + achar as reclamações dos clientes deles (= sua oportunidade).
- **Entra:** produto (ex: SmartTap) + concorrentes (você informa ou ele descobre via Busca).
- **Fontes:** Serper (site/Google), reviews, Instagram/TikTok deles, Reddit.
- **Sai:** relatório — o que copiar, gaps a explorar, alertas de preço, ideias pro Produto. Grava em `competitive_intel`.
- **Teste:** 1 produto + 1 concorrente, dry. **Risco:** baixo (só leitura).

**1.2 — Estrategista de Campanha (o "maestro")**
- **Objetivo:** dado um objetivo (lançar / promover / captar leads), planeja a campanha **completa (online E offline** — evento, parceria, PR, panfleto) e monta o briefing que vai acionar os agentes-peça.
- **Entra:** objetivo, produto, orçamento, prazo, público.
- **Sai:** plano de campanha + tarefas por agente (Copy, Creative, Ads, Social, Email, Vídeo). *v1 só gera o plano; acionar os agentes vem na Fase 4.*
- **Teste:** gerar plano pro SmartTap e revisar. **Risco:** baixo (não publica).

**1.3 — Agente de Analytics/Resultados + Growth (o "time técnico de resultado")**
- **Objetivo:** receber os números (Meta Ads, site, vendas) e transformar em relatório claro + recomendação (o que escalar, cortar, testar) pra devolver ao Estrategista.
- **Entra:** período + campanha/produto.
- **Fontes:** Meta Graph (insights), ledger do CFO (vendas), `social_interactions`.
- **Sai:** relatório de performance + próximo passo. Grava em `campaign_metrics`.
- **Teste:** rodar com os dados reais que já temos. **Risco:** baixo-médio (só leitura).

### FASE 2 — Peças que faltam *(agentes novos, isolados)*
- **Agente de Produto:** junta feedback (atendimento + espionagem) e vira roadmap de melhorias.
- **Agente de Operações:** estoque, fornecedor, produção, envio (importante pro SmartTap físico).
- **Agente de CRM/Leads:** acompanha cada lead do primeiro contato até a venda.

### FASE 3 — DMs (Messenger + Instagram Direct) *(extensão do atendimento)*
- Responder mensagem **privada**, não só comentário (AURA/NEXA). Extende o Social Inbox, que já funciona. **Risco:** moderado (mexe perto de algo que roda — feito com cuidado e teste).

### FASE 4 — Orquestração do CEO *(a mais delicada — por último, de propósito)*
- Ligar o **CEO** para chamar os agentes na ordem certa (ideia → aprovação → branding → landing → campanha → publicação).
- Ligar o **ATLAS** como porteiro de gasto (aprova até €50, escala acima).
- Ligar o **Modo Ideia** ao CEO (você joga um produto e a máquina roda).
- **Risco:** alto (toca vários). Feito passo a passo, com dry-run, sem gasto automático sem o ATLAS.

### FASE 5 — Endurecimento *(qualidade e segurança)*
- **Agente Dev/DevOps** fixo (monitora Sentry, corrige, provisiona).
- **Dashboard/BI** central (tudo num lugar).
- **Segurança:** rotacionar os tokens do Meta que passaram pelo chat; cache de tokens pra AURA/NEXA.

---

## Definição de "pronto" (por agente)
Um agente só é considerado pronto quando: rodou 1 teste real com sucesso, gravou no Cérebro, e está documentado (o que faz + como testar).

## O que NÃO faremos ainda (pra não dispersar)
- Publicação automática de Ads (Marketing API) — fica pra v2.
- Agente de TikTok publicando — depois.
- Vídeo (Higgsfield) — só quando tiver crédito.

---

## Próximo passo
Começar a **Fase 1**. Sugiro construir **um agente por vez**, seguindo a receita de 8 passos, testando cada um antes de ir pro próximo. A ordem sugerida dentro da Fase 1: **1.1 Espionagem → 1.2 Estrategista → 1.3 Analytics** (mas dá pra trocar).
