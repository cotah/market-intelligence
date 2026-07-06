# Market Intelligence AI

Sistema de agentes de IA que varre a internet continuamente em busca de oportunidades de negócio,
filtra pelo perfil do fundador e entrega apenas as ideias com alto potencial de execução.

---

## O que esse sistema faz

Em vez de você passar horas pesquisando tendências, o sistema faz isso por você de forma contínua.
Ele usa uma pipeline de 11 agentes especializados que trabalham em sequência:

1. Encontra o que está crescendo na internet
2. Valida se existe uma dor real por trás da tendência
3. Analisa a concorrência existente
4. Estima o tamanho do mercado
5. Verifica se IA pode resolver o problema
6. Filtra pelo perfil e capacidades do fundador
7. Define como monetizar
8. Calcula um score de 0 a 10
9. Gera um plano de negócio e MVP completo (apenas para scores acima de 8)
10. Tenta destruir a ideia (advogado do diabo)
11. Gera relatório diário com as melhores oportunidades

---

## Arquitetura

```
market-intelligence/
├── backend/                          # FastAPI + Python
│   ├── agents/                       # Os 11 agentes
│   │   ├── __init__.py
│   │   ├── trend_hunter.py           # Google Trends, Reddit, X, TikTok, PH, HN
│   │   ├── problem_hunter.py         # Reddit, Quora, Amazon Reviews, G2, Trustpilot
│   │   ├── competitor_hunter.py      # Busca quem já resolve o problema
│   │   ├── market_size.py            # TAM / SAM / SOM
│   │   ├── ai_opportunity.py         # Verifica se IA resolve o problema
│   │   ├── founder_compatibility.py  # Filtra pelo perfil do Henrique
│   │   ├── monetization.py           # Como ganhar dinheiro
│   │   ├── scorer.py                 # Score 0-10
│   │   ├── project_generator.py      # BMC + MVP + Roadmap (só para score >= 8)
│   │   ├── devils_advocate.py        # Tenta destruir a ideia
│   │   └── daily_report.py           # Relatório diário consolidado
│   ├── core/
│   │   ├── __init__.py
│   │   ├── pipeline.py               # Orquestra a sequência dos agentes
│   │   ├── llm.py                    # Wrapper Claude + OpenAI
│   │   ├── founder_profile.py        # Perfil completo do fundador
│   │   └── config.py                 # Configurações e variáveis de ambiente
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── perplexity.py             # Pesquisa de mercado profunda
│   │   ├── grok.py                   # Pesquisa no X/Twitter
│   │   ├── serper.py                 # Google Search
│   │   └── reddit.py                 # Reddit (mock por enquanto)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── opportunity.py            # Modelo de oportunidade no banco
│   │   └── report.py                 # Modelo de relatório diário
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py                 # Endpoints REST
│   │   └── schemas.py                # Pydantic schemas
│   ├── workers/
│   │   ├── __init__.py
│   │   └── pipeline_worker.py        # Celery tasks (pipeline contínuo)
│   ├── alembic/                      # Migrations do banco
│   ├── tests/
│   ├── main.py                       # Entry point FastAPI
│   ├── celery_app.py                 # Entry point Celery
│   ├── pyproject.toml                # Dependências (uv)
│   └── .env.example
├── frontend/                         # Next.js 15
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx              # Dashboard principal
│   │   │   ├── opportunities/        # Lista e detalhe de oportunidades
│   │   │   └── reports/              # Relatórios diários
│   │   ├── components/
│   │   │   ├── OpportunityCard.tsx
│   │   │   ├── ScoreBar.tsx
│   │   │   ├── PipelineStatus.tsx
│   │   │   └── DailyReport.tsx
│   │   └── lib/
│   │       └── api.ts                # Cliente para o backend
│   ├── package.json
│   └── .env.example
├── docker-compose.yml                # Redis + Postgres local
└── README.md
```

---

## Stack

| Camada | Tecnologia | Onde roda |
|--------|-----------|-----------|
| Backend API | FastAPI (Python) | Railway |
| Pipeline / Filas | Celery | Railway |
| Cache / Broker | Redis | Railway |
| Banco de dados | PostgreSQL | Railway |
| Frontend | Next.js 15 | Vercel |
| LLM principal | Claude (claude-sonnet-4-6) | API |
| LLM fallback | OpenAI (gpt-5.5) | API |
| Pesquisa de mercado | Perplexity (sonar-pro) | API |
| Pesquisa X/Twitter | Grok (grok-4.3) | API |
| Busca Google | Serper | API |
| Reddit | Mock (sem API key) | Local |

---

## Os 11 Agentes — Como Funcionam

### Agente 1 — Trend Hunter
**O que faz:** Encontra assuntos que estão crescendo agora.
**Fontes:** Google Trends (via Serper), X/Twitter (via Grok), Product Hunt, Hacker News, YouTube trending.
**Saída:** Lista de tópicos com sinal de crescimento e volume estimado.

### Agente 2 — Problem Hunter
**O que faz:** Para cada tópico do Trend Hunter, busca evidências de dor real.
**Fontes:** Reddit (mock), Perplexity (Quora, fóruns, reviews), Amazon Reviews (via Perplexity), G2/Trustpilot.
**Busca frases como:** "I hate...", "I wish...", "Why doesn't...", "There should be..."
**Saída:** Problemas confirmados com frases reais de usuários como evidência.

### Agente 3 — Competitor Hunter
**O que faz:** Para cada problema validado, mapeia quem já resolve.
**Busca:** Nome, preço, diferenciais, fraquezas reportadas por usuários.
**Saída:** Tabela de concorrentes com gaps identificados.

### Agente 4 — Market Size
**O que faz:** Estima TAM, SAM e SOM usando dados públicos.
**Método:** Perplexity para dados de mercado + Claude para cálculo e raciocínio.
**Saída:** Números com fonte e crescimento anual estimado.

### Agente 5 — AI Opportunity
**O que faz:** Avalia se o problema pode ser resolvido com IA.
**Resultado:** SIM / NÃO / PARCIALMENTE com justificativa.
**Saída:** Classificação + qual parte da solução a IA executa.

### Agente 6 — Founder Compatibility
**O que faz:** Compara o problema com o perfil do fundador.
**Verifica:** Skills necessárias vs disponíveis, gap de conhecimento, tempo estimado.
**Saída:** Score de compatibilidade, % de conhecimento disponível, tempo estimado de MVP.

### Agente 7 — Monetization
**O que faz:** Define os modelos de monetização viáveis.
**Opções:** Assinatura, Marketplace, Comissão, Ads, Licença, White Label, Hardware, API.
**Saída:** Top 2 modelos recomendados com estimativa de ticket médio.

### Agente 8 — Scorer
**O que faz:** Calcula score final da oportunidade de 0 a 10.
**Dimensões:**
- Mercado (peso 20%)
- Concorrência (peso 15%)
- Facilidade de execução (peso 15%)
- Escalabilidade (peso 15%)
- Potencial de IA (peso 20%)
- Potencial de lucro (peso 15%)
**Saída:** Score total e por dimensão. Oportunidades abaixo de 6 são descartadas.

### Agente 9 — Project Generator
**Ativado apenas quando:** Score >= 8.0
**O que faz:** Gera plano completo de negócio e MVP.
**Entrega:** Business Model Canvas, Features do MVP, Stack recomendada, Roadmap 90 dias, Estimativa de custo inicial.

### Agente 10 — Devil's Advocate
**O que faz:** Tenta destruir a ideia de propósito.
**Pergunta:** Por que vai falhar? Por que ninguém compra? Qual concorrente mata isso? Qual risco regulatório?
**Saída:** Lista de riscos reais com severidade. Evita paixão cega pela ideia.

### Agente 11 — Daily Report
**Executa:** Uma vez por dia (ou sob demanda).
**O que faz:** Consolida todas as oportunidades do dia em um relatório executivo.
**Saída:** Resumo com total analisado, promissoras, excelentes, e a melhor do dia com score.

---

## Perfil do Fundador (founder_profile.py)

O sistema usa esse perfil para filtrar oportunidades inviáveis antes de perder tempo analisando.

```python
FOUNDER_PROFILE = {
    "name": "Henrique",
    "location": "Dublin, Ireland",
    "languages": ["Portuguese", "English", "Italian", "Spanish", "Arabic"],
    "skills": {
        "technical": [
            "Python", "FastAPI", "Next.js", "REST APIs",
            "Automation", "AI/LLMs", "Claude Code", "NFC",
            "3D Printing", "WordPress"
        ],
        "business": [
            "Marketing", "B2B Sales", "SaaS", "E-commerce",
            "Product Management", "Community Building"
        ]
    },
    "markets": ["Ireland", "Europe", "Brazil", "Portuguese-speaking markets"],
    "active_projects": ["TALOA", "InMyHouses"],
    "budget_range": "bootstrap",
    "tools_available": [
        "Claude Code", "OpenAI", "Vercel", "Railway",
        "Supabase", "Stripe", "Canva", "GitHub"
    ],
    "target_business_type": ["SaaS", "Marketplace", "B2B", "Automation"],
    "avoid": ["physical_retail", "requires_large_team", "high_regulatory_overhead"]
}
```

---

## Pipeline de Execução

```
Trend Hunter
     ↓
Problem Hunter  ←── descarta se não há dor real
     ↓
Competitor Hunter
     ↓
Market Size
     ↓
AI Opportunity
     ↓
Founder Compatibility  ←── descarta se compatibilidade < 50%
     ↓
Monetization
     ↓
Scorer  ←── descarta se score < 6.0
     ↓
Devil's Advocate
     ↓
Project Generator  ←── só executa se score >= 8.0
     ↓
Salva no banco (PostgreSQL)
     ↓
Daily Report (consolida 1x por dia)
```

Cada agente que descarta uma ideia registra o motivo no banco antes de descartar.
Isso garante rastreabilidade completa de por que uma oportunidade foi eliminada.

---

## API Endpoints

```
GET  /health                          # Health check
GET  /opportunities                   # Lista todas as oportunidades
GET  /opportunities/{id}              # Detalhe de uma oportunidade
GET  /opportunities?score_min=8       # Filtrar por score
GET  /reports/daily                   # Lista relatórios diários
GET  /reports/daily/latest            # Relatório mais recente
POST /pipeline/start                  # Inicia pipeline manualmente
POST /pipeline/stop                   # Para o pipeline
GET  /pipeline/status                 # Status atual do pipeline
POST /pipeline/run-once               # Executa uma rodada agora e para
```

---

## Variáveis de Ambiente

### Backend (.env)
```env
# Banco de dados
DATABASE_URL=postgresql://user:password@host:5432/market_intelligence

# Redis (broker do Celery)
REDIS_URL=redis://host:6379/0

# LLMs
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Pesquisa
PERPLEXITY_API_KEY=pplx-...
GROK_API_KEY=xai-...
SERPER_API_KEY=...

# Reddit (deixar vazio para usar mock)
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=

# Pipeline
PIPELINE_INTERVAL_SECONDS=3600        # Roda a cada 1 hora
PIPELINE_TOPICS_PER_RUN=5             # Quantos tópicos por rodada
MIN_SCORE_TO_KEEP=6.0                 # Score mínimo para salvar
MIN_SCORE_FOR_PROJECT_PLAN=8.0        # Score para gerar plano completo

# App
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### Frontend (.env.local)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Como Rodar Localmente

### Pré-requisitos
- Python 3.12+
- Node.js 20+
- uv (gerenciador Python)
- Docker (para Redis e Postgres local)

### 1. Subir Redis e Postgres com Docker
```bash
docker-compose up -d
```

### 2. Backend
```bash
cd backend
uv sync
cp .env.example .env
# Editar .env com suas chaves

# Rodar migrations
uv run alembic upgrade head

# Iniciar API
uv run uvicorn main:app --reload --port 8000

# Em outro terminal, iniciar worker Celery
uv run celery -A celery_app worker --loglevel=info

# Em outro terminal, iniciar scheduler Celery (beat)
uv run celery -A celery_app beat --loglevel=info
```

### 3. Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
# Editar .env.local

npm run dev
# Acessa em http://localhost:3000
```

---

## Deploy em Producao (Railway + Vercel)

O backend (API + worker + beat + Postgres + Redis) roda no **Railway**.
O frontend roda na **Vercel**. O codigo ja esta preparado:

- `backend/Dockerfile` — imagem de producao (uv pinado); usada pelo Railway
- `backend/railway.toml` — aponta o build para o Dockerfile + healthcheck
- `backend/Procfile` — define os 3 processos: `web`, `worker`, `beat`
- `frontend/vercel.json` — config de build do Next.js
- `DATABASE_URL` / `REDIS_URL` do Railway sao lidos e normalizados automaticamente
- CORS controlado pela env `ALLOWED_ORIGINS`

### Passo 0 — Subir o codigo para o GitHub
Railway e Vercel fazem deploy a partir de um repo Git.
```bash
cd <raiz do projeto>   # pasta "busca"
git init
git add .
git commit -m "Market Intelligence AI"
# crie um repo no GitHub e:
git remote add origin https://github.com/<voce>/<repo>.git
git push -u origin main
```

### Passo 1 — Railway: banco e cache
1. Crie um **New Project** no Railway.
2. **+ New → Database → Add PostgreSQL**.
3. **+ New → Database → Add Redis**.

> Esses plugins expoem `DATABASE_URL` e `REDIS_URL` para os outros servicos.

### Passo 2 — Railway: servico da API (web)
1. **+ New → GitHub Repo** → selecione o repo.
2. Em **Settings** do servico:
   - **Root Directory:** `backend`
   - **Start Command:** deixe vazio (o `CMD` do Dockerfile roda migrations + uvicorn).
3. Em **Variables**, adicione (use referencia aos plugins):
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   - `REDIS_URL` = `${{Redis.REDIS_URL}}`
   - `ANTHROPIC_API_KEY` = sua chave
   - `OPENAI_API_KEY` = sua chave
   - `PERPLEXITY_API_KEY`, `GROK_API_KEY`, `SERPER_API_KEY` = suas chaves
   - `ENVIRONMENT` = `production`
   - `ALLOWED_ORIGINS` = (preenche no Passo 5, depois de ter a URL da Vercel)
4. Em **Settings → Networking → Generate Domain** para expor a API publicamente.
   Anote a URL (ex: `https://seu-backend.up.railway.app`).

### Passo 3 — Railway: servico do worker (Celery)
1. **+ New → GitHub Repo** → o **mesmo** repo (cria outro servico).
2. **Settings:**
   - **Root Directory:** `backend`
   - **Custom Start Command:** `uv run --no-sync celery -A celery_app worker --loglevel=info --concurrency=2`
   - **Networking:** sem dominio (nao e HTTP).
   - **Healthcheck:** deixe vazio (esse servico nao responde HTTP).
3. **Variables:** as mesmas do Passo 2 (DATABASE_URL, REDIS_URL e as chaves).
   Dica: use a aba **Variables → Shared** do projeto para nao repetir.

### Passo 4 — Railway: servico do beat (agendador)
1. **+ New → GitHub Repo** → o mesmo repo de novo.
2. **Settings:**
   - **Root Directory:** `backend`
   - **Custom Start Command:** `uv run --no-sync celery -A celery_app beat --loglevel=info`
   - Sem dominio, sem healthcheck.
3. **Variables:** as mesmas (DATABASE_URL, REDIS_URL, chaves).

> O `beat` dispara a rodada periodica (`PIPELINE_INTERVAL_SECONDS`) e o relatorio
> diario (23h UTC). A rodada periodica so executa quando a pipeline esta
> habilitada (botao **Start** no dashboard / `POST /pipeline/start`).

### Passo 5 — Vercel: frontend
1. Em vercel.com: **Add New → Project** → importe o mesmo repo do GitHub.
2. **Root Directory:** `frontend` (a Vercel detecta Next.js sozinha).
3. **Environment Variables:**
   - `NEXT_PUBLIC_API_URL` = a URL publica da API do Railway (Passo 2).
4. **Deploy.** Anote a URL final (ex: `https://seu-app.vercel.app`).

### Passo 6 — Fechar o CORS
1. Volte ao servico **web** no Railway → **Variables**.
2. Setar `ALLOWED_ORIGINS` = `https://seu-app.vercel.app` (sua URL da Vercel).
3. O servico reinicia e passa a aceitar so esse dominio.

### Passo 7 — Validar
- Abra `https://seu-backend.up.railway.app/health` → deve retornar `{"status":"ok"}`.
- Abra o app na Vercel → dashboard carrega as oportunidades.
- Clique **Run Once** → o worker processa uma rodada (veja os logs no Railway).

> **Local nao muda:** nada disso afeta o ambiente local. Continue usando
> `docker-compose` (Postgres 5434 / Redis 6380) e `uv run` normalmente.

---

## Roadmap

### Fase 1 — Foundation (semana 1-2)
- [ ] Setup do projeto (FastAPI + Celery + Redis + Postgres)
- [ ] Modelos do banco e migrations
- [ ] Perfil do fundador
- [ ] Wrapper LLM (Claude + OpenAI)
- [ ] Integrações: Perplexity, Grok, Serper
- [ ] Agentes 1-4 (Trend, Problem, Competitor, Market Size)
- [ ] Pipeline básico funcionando
- [ ] API endpoints

### Fase 2 — Agents (semana 2-3)
- [ ] Agentes 5-8 (AI Opportunity, Compatibility, Monetization, Scorer)
- [ ] Lógica de descarte por score
- [ ] Agente 9 (Project Generator)
- [ ] Agente 10 (Devil's Advocate)
- [ ] Agente 11 (Daily Report)
- [ ] Pipeline contínuo com Celery Beat

### Fase 3 — Frontend (semana 3-4)
- [ ] Dashboard com lista de oportunidades
- [ ] Filtros por score, data, status
- [ ] Detalhe de oportunidade (todos os dados dos agentes)
- [ ] Visualização do relatório diário
- [ ] Status em tempo real do pipeline

### Fase 4 — Deploy (semana 4)
- [ ] Backend no Railway
- [ ] Redis no Railway
- [ ] Postgres no Railway
- [ ] Frontend na Vercel
- [ ] Variáveis de ambiente configuradas
- [ ] Pipeline rodando em produção

---

## Modelo de Dados — Opportunity

```json
{
  "id": "uuid",
  "title": "AI Receptionist for Irish Barbershops",
  "summary": "...",
  "topic_origin": "AI Receptionist",
  "source": "trend_hunter",
  "status": "completed | in_progress | discarded",
  "discard_reason": null,

  "trend_data": { "growth_rate": "...", "volume": "..." },
  "problem_data": { "pain_phrases": [...], "sources": [...] },
  "competitor_data": { "competitors": [...], "gaps": [...] },
  "market_data": { "tam": "...", "sam": "...", "som": "..." },
  "ai_opportunity_data": { "verdict": "YES", "reasoning": "..." },
  "compatibility_data": { "score": 85, "gap": 15, "time_to_mvp": "3 months" },
  "monetization_data": { "models": [...], "recommended": "subscription" },
  "score_data": {
    "total": 9.2,
    "market": 9,
    "competition": 6,
    "ease": 8,
    "scalability": 10,
    "ai_potential": 10,
    "profit": 9
  },
  "project_plan": { "bmc": {...}, "mvp_features": [...], "roadmap": [...] },
  "devils_advocate_data": { "risks": [...], "fatal_flaws": [...] },

  "created_at": "2026-06-25T...",
  "updated_at": "2026-06-25T..."
}
```

---

## Como Adicionar um Novo Agente

1. Criar arquivo em `backend/agents/meu_agente.py`
2. Implementar classe herdando de `BaseAgent`
3. Implementar método `async def run(self, context: PipelineContext) -> AgentResult`
4. Registrar na pipeline em `backend/core/pipeline.py`
5. Adicionar campo de resultado no modelo `Opportunity`
6. Criar migration para o novo campo

---

## Decisões de Design

**Por que Claude como LLM principal?**
Claude tem melhor raciocínio analítico para avaliar oportunidades de negócio e é mais preciso
em tarefas que exigem julgamento. OpenAI é mantido como fallback.

**Por que Celery + Redis em vez de cron job simples?**
Permite controlar o pipeline em tempo real (start/stop via API), ver status de cada tarefa,
retry automático em falhas, e escalar workers independentemente.

**Por que descartar cedo na pipeline?**
Processar todos os 11 agentes para uma ideia ruim desperdiça tokens e tempo.
Cada agente tem critérios de descarte. Uma ideia sem dor real é eliminada no Agente 2,
antes de gastar análise de concorrência, mercado e compatibilidade.

**Por que Reddit em mock?**
A Reddit API tem restrições significativas para uso automatizado. O mock simula respostas
realistas. A integração real pode ser adicionada depois com PRAW quando tiver a API key.

---

## Contribuindo / Adicionando Fontes

Para adicionar uma nova fonte de dados (ex: LinkedIn, AppSumo, etc.):
1. Criar integração em `backend/integrations/nova_fonte.py`
2. Implementar método `async def search(self, query: str) -> list[dict]`
3. Importar no agente relevante (geralmente Problem Hunter ou Trend Hunter)
4. Documentar aqui no README
