"""Helpers de texto compartilhados entre agentes e integracoes."""

import re

_TOKEN_RE = re.compile(r"token=[^&\s'\"]+")


def redact_token(text: str) -> str:
    """Mascara valores de token=... antes de logar.

    str(HTTPStatusError) do httpx inclui a URL completa com ?token=... —
    sem isso, o token da Apify vaza nos logs (visto no Railway em
    2026-07-06).
    """
    return _TOKEN_RE.sub("token=***", text)


def to_hashtag(text: str) -> str:
    """Transforma texto livre em hashtag valida: lowercase, so alfanumerico.

    Remove "#", espacos, "&", hifens e qualquer outro caractere que os
    atores de Instagram/TikTok na Apify rejeitam (visto em producao em
    2026-07-06 com topicos longos do trend_hunter).
    """
    return "".join(ch for ch in text.lower() if ch.isalnum())
