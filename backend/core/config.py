"""Configuracoes da aplicacao, lidas do .env via Pydantic Settings.

Nunca hardcodar chaves: tudo vem daqui. Veja .env.example para os campos.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Banco ---
    # Local usa a porta 5434 (docker-compose). Em producao o Railway injeta
    # DATABASE_URL automaticamente; o validator abaixo normaliza o schema.
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5434/market_intelligence"

    # --- Redis ---
    # Local usa a porta 6380 (docker-compose). Railway injeta REDIS_URL.
    redis_url: str = "redis://localhost:6380/0"

    # --- LLMs ---
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # --- Integracoes ---
    perplexity_api_key: str = ""
    grok_api_key: str = ""
    serper_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    # --- Pipeline ---
    # No modo continuo a pipeline se auto-encadeia (ao terminar uma rodada
    # ja inicia a proxima). Por isso `pipeline_interval_seconds` deixa de ser
    # "1x por hora" e passa a ser apenas o watchdog do Celery Beat: de quanto
    # em quanto tempo o beat verifica se a cadeia morreu e a religa.
    pipeline_interval_seconds: int = 300
    # Intervalo entre uma rodada e a proxima no modo continuo (0 = imediato).
    # Um valor pequeno evita um loop apertado que martela as APIs externas.
    pipeline_continuous_gap_seconds: int = 5
    pipeline_topics_per_run: int = 5
    min_score_to_keep: float = 6.0
    min_score_for_project_plan: float = 8.0
    # Selo "Aprovado com ressalvas" (Opcao A, docs/PROPOSTA_SCORER_DEVILS_
    # ADVOCATE.md): thresholds do Devil's Advocate que ativam o risk_flag.
    # A nota NUNCA muda — apenas o selo.
    risk_flag_min_fatal_flaws: int = 2
    risk_flag_min_high_risks: int = 3

    # --- App ---
    environment: str = "development"
    log_level: str = "INFO"

    # CORS: dominios permitidos em producao, separados por virgula.
    # Vazio = libera tudo (modo dev). Em producao, setar para a URL da Vercel.
    allowed_origins: str = ""

    # Modelos de LLM / integracoes (o melhor disponivel de cada provedor,
    # verificado via API em 2026-06-25). Sobrescreviveis pelo .env.
    anthropic_model: str = "claude-sonnet-4-6"   # principal
    openai_model: str = "gpt-5.5"                # fallback (mais recente da OpenAI)
    perplexity_model: str = "sonar-pro"          # pesquisa (familia sonar atual)
    grok_model: str = "grok-4.3"                 # pesquisa no X (melhor xAI)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        """Railway injeta a URL como 'postgres://' ou 'postgresql://'.
        O SQLAlchemy async exige o driver asyncpg. Convertemos aqui.
        URLs que ja tem '+asyncpg' (local) passam intactas."""
        if v.startswith("postgresql+"):
            return v
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        """Lista de origens para o CORS. Vazio => ['*'] (dev)."""
        origins = [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
        return origins or ["*"]


settings = Settings()
