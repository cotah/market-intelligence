# CLAUDE.md — Instruções para Claude Code

## O que é esse projeto

Market Intelligence AI — pipeline de 11 agentes de IA que varre a internet continuamente
em busca de oportunidades de negócio, filtra pelo perfil do fundador e entrega apenas
as ideias com alto potencial de execução.

Leia o README.md completo antes de qualquer coisa. Ele é o norte de todo o projeto.

---

## Stack obrigatória

- Backend: FastAPI + Python 3.12
- Gerenciador de deps: uv (não pip, não poetry)
- Banco: PostgreSQL + SQLAlchemy 2.0 (async) + Alembic
- Filas: Celery + Redis
- Frontend: Next.js 15 + TypeScript + Tailwind CSS
- LLMs: Anthropic SDK (principal) + OpenAI SDK (fallback)
- Testes: pytest + pytest-asyncio

---

## Fase atual: FASE 1 — Foundation

Execute nesta ordem exata. Não pule etapas.

### Passo 1 — Estrutura do projeto backend

Criar a estrutura de pastas conforme o README.md.

```
backend/
├── agents/
│   └── __init__.py
├── core/
│   └── __init__.py
├── integrations/
│   └── __init__.py
├── models/
│   └── __init__.py
├── api/
│   └── __init__.py
├── workers/
│   └── __init__.py
├── alembic/
├── tests/
├── main.py
├── celery_app.py
└── pyproject.toml
```

### Passo 2 — pyproject.toml

Criar com estas dependências:

```toml
[project]
name = "market-intelligence-backend"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.30.0",
    "alembic>=1.13.0",
    "celery[redis]>=5.4.0",
    "redis>=5.0.0",
    "anthropic>=0.40.0",
    "openai>=1.50.0",
    "httpx>=0.27.0",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.4.0",
    "python-dotenv>=1.0.0",
    "structlog>=24.0.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-httpx>=0.30.0",
    "httpx>=0.27.0",
]
```

### Passo 3 — core/config.py

Criar configuração com Pydantic Settings lendo do .env:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Banco
    database_url: str
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # LLMs
    anthropic_api_key: str
    openai_api_key: str = ""
    
    # Integrações
    perplexity_api_key: str = ""
    grok_api_key: str = ""
    serper_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    
    # Pipeline
    pipeline_interval_seconds: int = 3600
    pipeline_topics_per_run: int = 5
    min_score_to_keep: float = 6.0
    min_score_for_project_plan: float = 8.0
    
    # App
    environment: str = "development"
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### Passo 4 — models/opportunity.py

Criar modelo SQLAlchemy com TODOS os campos do modelo de dados descrito no README.md.
Usar JSONB para campos como trend_data, problem_data, competitor_data etc.
Adicionar índices em: score_total, created_at, status.

### Passo 5 — core/llm.py

Wrapper que tenta Claude primeiro, cai para OpenAI se falhar.

```python
async def ask(
    prompt: str,
    system: str = "",
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> str:
    # Tenta Anthropic primeiro
    # Se falhar (exception ou key vazia), tenta OpenAI
    # Se ambos falharem, lança exceção clara
```

### Passo 6 — core/founder_profile.py

Criar o perfil do fundador exatamente como descrito no README.md.
Adicionar função `get_profile_as_text() -> str` que retorna o perfil formatado
para ser inserido nos prompts dos agentes.

### Passo 7 — Integrações

Criar cada integração em `integrations/`:

**perplexity.py**
```python
async def search(query: str, focus: str = "internet") -> str:
    # POST para https://api.perplexity.ai/chat/completions
    # model: "llama-3.1-sonar-large-128k-online"
    # Retorna o conteúdo da resposta como string
```

**grok.py**
```python
async def search_x(query: str) -> str:
    # POST para https://api.x.ai/v1/chat/completions  
    # model: "grok-3"
    # Focado em pesquisar discussões no X/Twitter
    # Retorna o conteúdo como string
```

**serper.py**
```python
async def google_search(query: str, num_results: int = 10) -> list[dict]:
    # POST para https://google.serper.dev/search
    # Retorna lista de resultados com title, link, snippet
```

**reddit.py**
```python
async def search_reddit(subreddit: str, query: str) -> list[dict]:
    # MODO MOCK — retornar dados simulados realistas
    # Documentar claramente que é mock
    # Estrutura: [{"title": str, "body": str, "upvotes": int, "subreddit": str}]
```

### Passo 8 — Agente base

Criar `agents/base.py`:

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class PipelineContext:
    """Contexto compartilhado entre todos os agentes na pipeline."""
    topic: str                    # Tópico sendo analisado
    opportunity_id: str           # ID no banco
    trend_data: dict = None
    problem_data: dict = None
    competitor_data: dict = None
    market_data: dict = None
    ai_opportunity_data: dict = None
    compatibility_data: dict = None
    monetization_data: dict = None
    score_data: dict = None
    project_plan: dict = None
    devils_advocate_data: dict = None
    should_discard: bool = False
    discard_reason: str = ""

@dataclass  
class AgentResult:
    success: bool
    data: dict
    should_discard: bool = False
    discard_reason: str = ""
    error: str = ""

class BaseAgent:
    name: str = "base"
    
    async def run(self, context: PipelineContext) -> AgentResult:
        raise NotImplementedError
```

### Passo 9 — Agente 1: Trend Hunter

Criar `agents/trend_hunter.py`.

Prompt para o LLM usando Serper + Grok como fonte de dados:
1. Usar Serper para buscar "trending topics {current_month}" e variações
2. Usar Grok para buscar o que está sendo discutido no X agora
3. Usar Perplexity para confirmar tendências no Product Hunt e Hacker News
4. Consolidar com Claude e retornar lista de 5-10 tópicos com score de crescimento

Saída esperada:
```python
{
    "topics": [
        {
            "name": "AI Receptionist",
            "growth_signal": "high",
            "sources": ["X/Twitter", "Product Hunt"],
            "evidence": "...",
            "search_volume_trend": "increasing"
        }
    ]
}
```

### Passo 10 — Agente 2: Problem Hunter

Criar `agents/problem_hunter.py`.

Para cada tópico do Trend Hunter:
1. Usar Perplexity para buscar reclamações e dores relacionadas
2. Usar Reddit mock para simular discussões
3. Prompt para Claude identificar frases de dor ("I hate", "I wish", etc.)
4. Se não encontrar dor real → discard com motivo

Critério de descarte: menos de 3 evidências de dor real.

### Passo 11 — main.py e API básica

Criar FastAPI app com:
- Todos os endpoints do README.md
- Health check funcionando
- CORS configurado
- Logging estruturado com structlog

### Passo 12 — docker-compose.yml

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: market_intelligence
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

### Passo 13 — .env.example

Criar com todos os campos de Settings mas sem valores reais.

---

## Após Fase 1 completa

Avisar o usuário que a Fase 1 está concluída e perguntar se pode avançar para a Fase 2
(Agentes 3-11 + pipeline completo).

---

## Regras obrigatórias

1. Sempre async/await — sem código síncrono bloqueante
2. Typing em tudo — sem Any desnecessário
3. Tratamento de exceções em toda chamada externa
4. Logs claros em cada etapa da pipeline
5. Nunca hardcodar chaves — sempre via Settings
6. Cada agente deve funcionar mesmo se uma integração externa falhar (graceful degradation)
7. Commits atômicos — um commit por funcionalidade
8. Testes para os agentes principais

---

## Convenções de código

```python
# Nomear agentes sempre assim:
class TrendHunterAgent(BaseAgent):
    name = "trend_hunter"
    
# Logs sempre assim:
import structlog
log = structlog.get_logger()
log.info("trend_hunter.started", topic=topic)
log.info("trend_hunter.completed", topic=topic, results_count=len(results))

# Erros sempre assim:
log.error("trend_hunter.failed", topic=topic, error=str(e))
raise AgentException(f"TrendHunter failed for topic '{topic}': {e}") from e
```

---

## O que NÃO fazer

- Não usar Flask, Django ou qualquer outro framework além de FastAPI
- Não usar pip diretamente — sempre uv
- Não criar endpoints síncronos
- Não colocar lógica de negócio nos endpoints — fica nos agentes/services
- Não commitar .env
- Não fazer refactor de código que já funciona
- Não pular para a Fase 2 sem a Fase 1 estar completa e testada
