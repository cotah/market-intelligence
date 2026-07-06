"""Helpers de texto compartilhados entre agentes e integracoes."""


def to_hashtag(text: str) -> str:
    """Transforma texto livre em hashtag valida: lowercase, so alfanumerico.

    Remove "#", espacos, "&", hifens e qualquer outro caractere que os
    atores de Instagram/TikTok na Apify rejeitam (visto em producao em
    2026-07-06 com topicos longos do trend_hunter).
    """
    return "".join(ch for ch in text.lower() if ch.isalnum())
