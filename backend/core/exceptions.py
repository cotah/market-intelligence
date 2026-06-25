"""Excecoes customizadas do sistema."""


class MarketIntelligenceError(Exception):
    """Base para todos os erros da aplicacao."""


class AgentException(MarketIntelligenceError):
    """Erro durante a execucao de um agente da pipeline."""


class LLMException(MarketIntelligenceError):
    """Erro ao chamar os provedores de LLM (Claude / OpenAI)."""


class IntegrationException(MarketIntelligenceError):
    """Erro em uma integracao externa (Perplexity, Grok, Serper, Reddit)."""
