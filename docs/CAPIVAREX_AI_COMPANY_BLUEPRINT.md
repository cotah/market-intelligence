# Capivarex AI Company — Blueprint Completo

**Objetivo:** transformar o Growth Agency AI (que hoje só gera landing pages) numa **empresa de IA completa, white-label**, onde times inteiros de agentes trabalham juntos — pesquisa, criação, desenvolvimento, marketing, vendas, atendimento, financeiro, jurídico e administração — sempre buscando o melhor resultado pro produto/serviço do cliente.

Motor principal: **Claude Fable 5**, orquestrado via n8n, com um "cérebro compartilhado" (Supabase) que todos os agentes consultam e alimentam.

---

## 0. Como ler este documento (rapidinho, sem enrolação)

Cada departamento abaixo tem:
- **O que faz** — em português simples
- **O que já existe hoje** — o que já construímos
- **O que falta** — o que precisa ser criado
- **Integrações/APIs necessárias**
- **Prioridade** — P0 (essencial pra empresa funcionar), P1 (importante, logo em seguida), P2 (retoque/expansão depois)
- **Precisa de aprovação humana?** — sim/não, e onde

---

## 0.1 Regra de arquitetura obrigatória — Edição Granular (não regenerar tudo do zero)

**Adicionado em 02/07/2026, após a experiência real de retrabalho na landing page de um produto piloto.**

**O problema que aconteceu:** toda vez que uma imagem ou texto da landing page não ficava bom, o sistema regenerava a página inteira do zero — gastando tokens à toa, arriscando perder partes que já estavam boas, e sem controle real do que mudou.

**A regra daqui pra frente:** todo agente que gera uma "peça" (imagem, texto, seção, post, vídeo) precisa registrar essa peça de forma **identificável e isolada** no Cérebro Compartilhado (seção 12.1), não só entregar um bloco único de resultado final.

Isso significa que, quando você disser algo como *"não gostei dessa imagem do hero"* ou *"muda só o preço na seção de pricing"*, o Orchestrator (seção 2.1) precisa conseguir:

1. Identificar exatamente qual peça você está apontando
2. Chamar **só o agente responsável por aquela peça** (ex: só o Creative Agent pra imagem, só o Copy Agent pra texto)
3. Atualizar **só aquele pedaço** no Cérebro Compartilhado
4. Publicar de novo, mantendo tudo o que não foi tocado exatamente como estava

**Isso vale pra toda área da empresa, não só landing page:** imagem de post de social media, parágrafo de email de vendas, cena de um vídeo, resposta padrão do customer service — qualquer peça gerada por qualquer agente deve poder ser editada isoladamente.

**Impacto no plano:** isso muda o antigo item "Editor Agent" (que estava isolado lá na Fase 4) — ele deixa de ser um agente separado no futuro e vira um **princípio de arquitetura obrigatório desde a Fase 0**. O Cérebro Compartilhado já nasce estruturado em peças endereçáveis, e o Orchestrator já nasce sabendo rotear edição pontual, não só criação do zero.

Exemplo de como uma landing page fica registrada no Cérebro Compartilhado, na prática:
```
landing_produto: {
  hero_image: { url: "...", agent: "creative", version: 3 },
  hero_text: { content: "...", agent: "copy", version: 1 },
  pricing_text: { content: "...", agent: "copy", version: 2 },
  features_image: { url: "...", agent: "creative", version: 1 }
}
```
Cada peça tem seu próprio histórico de versão — dá até pra "voltar pra versão anterior" se quiser, sem precisar gerar de novo.

---



## 1. Visão geral — como a empresa vai funcionar

Pensa numa empresa de verdade. Ela tem departamentos, cada departamento tem pessoas, e todo mundo se reporta pra uma liderança que decide prioridades. Aqui é igual, só que cada "pessoa" é um agente de IA especializado, e cada "departamento" é uma sessão de agentes trabalhando juntos numa tarefa.

```
                    ┌─────────────────────────┐
                    │   CAMADA EXECUTIVA       │
                    │  (Orchestrator / CEO)    │
                    └───────────┬─────────────┘
                                │
        ┌───────────┬──────────┼──────────┬───────────┬──────────┐
        ▼           ▼          ▼          ▼           ▼          ▼
   Pesquisa &    Criativo   Dev/Tech   Marketing   Vendas &    Financeiro
  Oportunidades                                    Social      & Jurídico
        │           │          │          │           │          │
        └───────────┴──────────┴──────────┴───────────┴──────────┘
                                │
                    ┌───────────▼─────────────┐
                    │   CÉREBRO COMPARTILHADO  │
                    │  (Supabase — Brand Kit,  │
                    │   memória, histórico,    │
                    │   métricas, aprendizado) │
                    └──────────────────────────┘
```

**Regra de ouro:** nenhum agente trabalha isolado. Todo agente lê o Cérebro Compartilhado antes de agir (pra saber marca, tom de voz, produto, dados do cliente) e escreve nele depois (pra registrar o que fez, e os outros agentes saberem).

---

## 2. Camada Executiva — o "C-Level" da empresa de IA

### 2.1 Orchestrator Agent (CEO)
**O que faz:** recebe o pedido (ex: "lança o produto X pro público Y"), decide qual sequência de departamentos precisa agir, dispara cada um na ordem certa, e junta os resultados no final.

**O que já existe hoje:** nada ainda — cada agente roda separado, você dispara um por um manualmente.

**O que falta:** workflow master no n8n que recebe um único webhook e orquestra toda a cadeia (Pesquisa → Estratégia → Criativo → Dev → Marketing → Vendas), com lógica de decisão (se faltar informação, pede mais contexto; se um passo falhar, avisa em vez de travar tudo).

**Prioridade:** P0 — é a espinha dorsal de tudo.

**Aprovação humana:** não precisa pra rodar, mas deve sempre te avisar o que fez (relatório automático por email/WhatsApp no fim da execução).

### 2.2 CFO Agent (Financeiro)
Ver seção 9.

### 2.3 Partner/Strategy Agent
**O que faz:** revisa decisões grandes antes de executar — tipo um sócio que dá segunda opinião. Cruza dados do Research Agent com a Brand Context e sinaliza riscos ou oportunidades que os outros agentes sozinhos não veriam.

**O que falta:** tudo — é um agente de "revisão estratégica" que roda entre a Pesquisa e a Execução, avaliando se o plano faz sentido antes de gastar tokens/dinheiro executando.

**Prioridade:** P1.

**Aprovação humana:** não obrigatória, mas recomendado revisar o relatório dele antes de aprovar campanhas grandes.

---

## 3. Departamento de Pesquisa & Oportunidades

Junta o que você já tem (Research Agent do Growth Agency + Market Intelligence AI de 11 agentes) numa coisa só.

**O que faz:** 
- Pesquisa mercado, concorrência, dores do público-alvo
- Escaneia oportunidades de negócio (isso já existe no Market Intelligence AI)
- Alimenta o Cérebro Compartilhado com tudo que descobre, pra outros agentes usarem

**O que já existe hoje:** ✅ Research Agent (Growth Agency) + ✅ Market Intelligence AI (11 agentes, rodando em produção)

**O que falta:** unificar os dois sistemas — hoje eles rodam separados, sem conversar entre si. Precisa de uma ponte: quando o Market Intelligence encontra uma oportunidade, ela deveria automaticamente virar um "brief" pro Research Agent aprofundar.

**Integrações:** Perplexity, Brave Search (já configurado)

**Prioridade:** P0 — já está 90% pronto, só falta a ponte.

**Aprovação humana:** não.

---

## 4. Departamento Criativo

**O que faz:** copywriting, geração de imagem, geração de landing page, (futuramente) vídeo e design de identidade visual completa.

**O que já existe hoje:** ✅ Copy Agent, ✅ Creative Agent (imagens), ✅ Landing Page Agent — os três já funcionam e já estão testados.

**O que falta:**
- **Video Agent** (via Higgsfield) — gera vídeos promocionais usando as imagens já no Supabase
- **Brand Identity Agent** — cria logo, paleta de cores e guia de marca completo pra produtos novos (hoje isso é feito manualmente por você)
- ~~Editor Agent~~ — **não é mais um agente separado**: virou princípio de arquitetura (ver seção 0.1), já embutido no Orchestrator desde a Fase 0

**Integrações necessárias:** Higgsfield (já conectado como MCP), Canva (já conectado como MCP) — pode ser usado pra gerar documentos/apresentações de marca

**Prioridade:** P0 pro que já existe (manter funcionando), P1 pro Video Agent, P2 pro Brand Identity e Editor.

**Aprovação humana:** não, mas recomendado revisar antes de publicar em produção real pra clientes.

---

## 5. Departamento de Desenvolvimento (Dev/Tech Agent)

**O que faz:** essa é a parte mais delicada — um agente que ajuda a **escrever código, revisar PRs, rodar testes, e sugerir correções**, sempre com humano aprovando antes do deploy.

**O que já existe hoje:** você já usa o Claude Code manualmente pra isso — funciona muito bem, como vimos nas correções da landing page.

**O que falta:** formalizar isso como parte do "time" — um agente que:
- Recebe bugs reportados pelo Customer Service Agent (seção 8) automaticamente
- Investiga a causa
- Propõe a correção (nunca aplica sozinho em produção sem aprovação)
- Roda testes antes de sugerir o merge

**Integrações:** GitHub (já conectado), Claude Code (já em uso)

**Prioridade:** P1 — o Claude Code manual já resolve isso por enquanto, automatizar é uma melhoria, não uma urgência.

**Aprovação humana:** **SIM, sempre.** Nenhum código vai pra produção sem você (ou alguém do time) revisar e aprovar o PR. Isso é inegociável — é a mesma regra que qualquer empresa de software séria segue.

---

## 6. Departamento de Marketing

**O que faz:** campanhas pagas (Google Ads, Meta Ads), SEO, email marketing, e planejamento de calendário de conteúdo.

**O que já existe hoje:** nada formalizado ainda — Copy Agent gera texto, mas não gerencia campanha.

**O que falta:**
- **Ads Agent** — cria e otimiza campanhas no Google Ads / Meta Ads
- **SEO Agent** — audita o site, sugere melhorias técnicas e de conteúdo
- **Email Agent** — sequências de nutrição e campanhas (já estava no seu roadmap anterior)
- **Naming/Virality Agent** (que você pediu) — gera nomes de produto, taglines, hooks virais

**Integrações necessárias:** Google Ads API, Meta Marketing API, Resend (você já usa em outro produto, dá pra reaproveitar)

**Prioridade:** P1.

**Aprovação humana:** sim, pra qualquer campanha que gaste dinheiro real (ads pagos) — o agente prepara a campanha, você aprova o orçamento antes de ativar.

---

## 7. Departamento de Redes Sociais

**O que faz:** cria posts, define calendário, publica automaticamente ou deixa em rascunho pra aprovação.

**O que já existe hoje:** nada ainda.

**O que falta:** Social Media Agent completo — gera o post (usando o Copy + Creative Agent como base), agenda, e publica.

**Integrações necessárias:** Meta Graph API (Instagram/Facebook), possivelmente Buffer ou Later como camada de agendamento (mais simples que integrar direto com cada rede)

**Prioridade:** P1.

**Aprovação humana:** recomendado no início (revisar antes de publicar), pode virar automático depois que a qualidade for validada por algumas semanas.

---

## 8. Departamento de Vendas & Customer Service

### 8.1 Sales Agent
**O que faz:** prospecção (encontra leads), qualifica, e envia outreach personalizado.

**O que falta:** tudo — desde a lista de prospecção (pode vir do Market Intelligence AI) até o disparo de mensagens.

**Integrações necessárias:** Gmail (já conectado), LinkedIn Sales Navigator (se quiser prospecção B2B mais robusta), CRM (ver seção 11)

**Prioridade:** P1.

### 8.2 Customer Service Agent
**O que faz:** responde dúvidas de clientes, resolve problemas simples, escala pra você quando não sabe resolver.

**O que falta:** tudo — um agente conectado ao WhatsApp Business (você já tem isso configurado em outro produto!) que responde automaticamente, e escala casos complexos.

**Integrações necessárias:** WhatsApp Business API (já configurada em outro produto), um sistema de helpdesk simples (pode ser até uma tabela no Supabase pra começar, sem precisar de ferramenta paga)

**Prioridade:** P0 pro produto que já tem WhatsApp bot, já que ele existe — só falta ligar ele numa lógica de "empresa" mais ampla.

**Aprovação humana:** não pra dúvidas simples, sim pra qualquer coisa envolvendo reembolso, cancelamento ou reclamação séria.

---

## 9. Departamento Financeiro (CFO Agent)

**O que faz:** acompanha receita, despesas, métricas financeiras (MRR, churn, CAC, LTV), e gera relatórios.

**O que NÃO faz sozinho:** mover dinheiro, fazer pagamentos, ou tomar decisões financeiras vinculantes. Isso é regra de segurança, não limitação técnica.

**O que já existe hoje:** Stripe já está conectado (visto nas suas abas abertas), mas sem agente analisando os dados.

**O que falta:** 
- Dashboard automático de métricas financeiras (lê do Stripe, organiza, resume)
- Alertas automáticos (ex: "churn subiu 15% esse mês", "MRR cresceu")
- Projeções simples baseadas em dados reais

**Integrações necessárias:** Stripe API (já conectado)

**Prioridade:** P1.

**Aprovação humana:** **SIM, sempre**, pra qualquer ação que envolva dinheiro de verdade (reembolsos, mudanças de preço, etc). O agente analisa e recomenda — você decide.

---

## 10. Departamento Jurídico (Legal Agent)

**O que faz:** gera rascunhos de termos de uso, política de privacidade, e revisa qualquer texto legal usado no produto.

**O que já existe hoje:** nada — os termos atuais provavelmente foram feitos manualmente ou com template genérico.

**O que falta:** 
- Legal Agent que gera rascunhos de Termos de Serviço e Política de Privacidade, considerando GDPR (você opera na Irlanda/UE, isso é levado a sério)
- Checklist de compliance pra cada produto novo antes de lançar

**Integrações necessárias:** nenhuma API específica — é trabalho de geração de texto + pesquisa de regulamentação

**Prioridade:** P1 — importante, mas os produtos atuais (ex.: TALOA) já estão rodando, então não é bloqueante imediato.

**Aprovação humana:** **SIM, SEMPRE, sem exceção.** O agente prepara o rascunho, mas um advogado real (ou você, com cuidado) precisa revisar antes de publicar qualquer termo legal. Isso protege você de verdade — termo de privacidade errado pode gerar multa de GDPR.

---

## 11. Departamento Administrativo / Operações

**O que faz:** organiza documentação interna, gerencia tarefas entre os outros agentes, mantém o Cérebro Compartilhado atualizado, cuida de "housekeeping" (limpar dados de teste, arquivar logs antigos, etc).

**O que falta:** tudo — é o agente "faxineiro e organizador" que garante que o resto da empresa não vira bagunça.

**Prioridade:** P2 — não urgente, mas evita que o sistema fique desorganizado conforme cresce.

**Aprovação humana:** não.

---

## 12. Infraestrutura compartilhada (a parte mais importante tecnicamente)

### 12.1 O "Cérebro Compartilhado" (Brand & Company Context)

Hoje, cada agente tem as informações da marca "hardcoded" dentro do próprio prompt (você viu isso — tivemos que editar o prompt do Claude Build HTML toda vez que queria mudar algo). Isso não escala.

**O que precisa ser feito:**
Criar uma tabela no Supabase chamada `company_brain` com:
- Dados de marca de cada produto (cores, tom de voz, público-alvo, preço)
- Histórico de decisões (o que já foi tentado, o que funcionou, o que não funcionou)
- Métricas atuais (pra agentes saberem o contexto antes de agir)

Todo agente, antes de começar a trabalhar, consulta essa tabela. Isso resolve o problema de "toda vez que preciso mudar algo, preciso editar o prompt manualmente".

**Prioridade:** P0 — isso é a base que faz a empresa funcionar como empresa, e não como um monte de scripts soltos.

**Implementado em 02/07/2026:** projeto Supabase dedicado criado separadamente de qualquer produto, especificamente para o Company Brain. URL: https://bybocxguyoejfdhlszpo.supabase.co. Tabelas `company_brain` e `brand_context` já criadas via SQL, com seed inicial do produto piloto. Credencial salva no n8n como 'Capivarex Brain Supabase'.

### 12.2 Orquestração (n8n)
Já é a ferramenta certa — só precisa crescer de "4 workflows soltos" pra "1 workflow master + sub-workflows por departamento".

### 12.3 Observabilidade
**O que falta:** um lugar único onde você vê o que cada agente fez, quando, e se deu certo — hoje você descobre erro só quando abre o n8n manualmente. Um relatório diário resumido (por email ou WhatsApp) resolveria isso.

**Prioridade:** P1.

---

## 13. Tabela de integrações — o que já temos vs o que falta

| Integração | Status | Usado por |
|---|---|---|
| Anthropic (Claude) | ✅ Conectado | Todos os agentes de texto/estratégia |
| OpenAI (GPT Image) | ✅ Conectado | Creative Agent |
| Supabase | ✅ Conectado | Storage, banco de dados, futuro Cérebro Compartilhado |
| GitHub | ✅ Conectado | Deploy, Dev Agent |
| Perplexity / Brave Search | ✅ Conectado | Research Agent |
| Stripe | ✅ Conectado (visto nas abas) | Financeiro (falta o agente) |
| WhatsApp Business API | ✅ Conectado (produto piloto) | Customer Service (falta ligar ao resto) |
| Higgsfield | ✅ Conectado (MCP) | Video Agent (falta construir) |
| Canva | ✅ Conectado (MCP) | Brand Identity Agent (falta construir) |
| Google Ads API | ❌ Falta | Marketing/Ads Agent |
| Meta Marketing API | ❌ Falta | Marketing/Ads Agent, Social Media Agent |
| Meta Graph API (posts) | ❌ Falta | Social Media Agent |
| Gmail | ✅ Conectado | Sales Agent |
| CRM (ex: HubSpot free, ou tabela Supabase própria) | ❌ Falta | Sales Agent |
| E-signature (ex: DocuSign, ou Docuseal que você já usa no InMyHouses) | ✅ Já usado em outro projeto | Legal Agent, Vendas |
| Helpdesk (pode começar simples, com Supabase) | ❌ Falta | Customer Service Agent |

---

## 14. Roadmap — ordem recomendada de construção

### Fase 0 — Fundação (antes de criar mais agentes)
1. Cérebro Compartilhado no Supabase (seção 12.1)
2. Orchestrator Agent — workflow master (seção 2.1)

Sem isso, cada agente novo que a gente criar vai ter o mesmo problema que tivemos com a landing page — informação espalhada, difícil de manter.

### Fase 1 — Fechar o que já está quase pronto
3. Ponte entre Research Agent e Market Intelligence AI (seção 3)
4. Customer Service Agent ligado ao WhatsApp já existente (seção 8.2)
5. CFO Agent — dashboard de métricas via Stripe (seção 9)

### Fase 2 — Expandir criação e marketing
6. Video Agent (Higgsfield)
7. Social Media Agent
8. Email Agent
9. Naming/Virality Agent

### Fase 3 — Vendas e crescimento
10. Sales Agent (prospecção + outreach)
11. Ads Agent (Google/Meta)
12. SEO Agent

### Fase 4 — Governança e proteção (importante antes de vender pra clientes reais)
13. Legal Agent (termos, privacidade) — **com revisão humana obrigatória**
14. ~~Editor Agent~~ — já resolvido na Fase 0 (é princípio de arquitetura, não agente separado — ver seção 0.1)
15. Departamento Administrativo (organização geral)

### Fase 5 — Refino
16. Partner/Strategy Agent (segunda opinião estratégica)
17. Brand Identity Agent (logo, identidade visual completa)
18. Melhorias visuais avançadas (GSAP, Three.js — já no roadmap anterior)

---

## 15. Regras de governança (não negociáveis)

Pra essa empresa ser confiável — pra você e pra futuros clientes white-label — algumas regras precisam existir desde o início:

1. **Legal e Financeiro nunca agem sozinhos.** Preparam, você aprova.
2. **Nenhum código vai pra produção sem revisão humana do PR.**
3. **Nenhuma campanha paga (ads) é ativada sem aprovação de orçamento.**
4. **Todo agente registra o que fez no Cérebro Compartilhado** — isso cria um histórico auditável, então se algo der errado, dá pra rastrear exatamente onde.
5. **Dados sensíveis de clientes nunca aparecem em logs ou prints** — mesma lição que aprendemos com os tokens do GitHub expostos.

---

## 16. O que significa "100%, top do top" nesse contexto

Não é sobre ter 30 agentes por ter. É sobre:

- Cada departamento realmente **entregar valor real**, testado, sem gambiarra
- A empresa conseguir **rodar do início ao fim** (pesquisa → criação → lançamento → venda → suporte) com o mínimo de intervenção manual, mas com os portões de segurança certos nos lugares certos
- Ser **reutilizável pra qualquer produto novo** (TALOA, ou um cliente white-label futuro) só trocando o Cérebro Compartilhado, sem reescrever os agentes
- Você conseguir **confiar** no sistema — saber o que ele fez, por quê, e poder reverter se precisar

---

## 17. Próximo passo imediato

Recomendo começarmos pela **Fase 0** — Cérebro Compartilhado + Orchestrator. É o que menos aparece visualmente (não é uma landing page bonita), mas é o que faz todo o resto funcionar como empresa de verdade, em vez de workflows soltos.

Quer que eu monte o schema do Cérebro Compartilhado no Supabase primeiro, ou prefere começar pelo Orchestrator Agent?
