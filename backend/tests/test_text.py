"""Testes do helper de texto compartilhado (core/text.py).

to_hashtag: transforma texto livre em hashtag valida (lowercase, so
alfanumerico). Criado apos a validacao real de 2026-07-06, quando
hashtags derivadas de topicos com "&" e hifens quebravam os atores
de Instagram/TikTok na Apify.
"""

from core.text import redact_token, to_hashtag


def test_to_hashtag_lowercases_and_removes_spaces():
    assert to_hashtag("AI Receptionist") == "aireceptionist"


def test_to_hashtag_strips_hash_prefix():
    assert to_hashtag("#AIAgents") == "aiagents"


def test_to_hashtag_removes_non_alphanumeric():
    # Casos reais de producao (2026-07-06): & e hifen geravam tags invalidas.
    assert (
        to_hashtag("Synthetic Media Version Control & Rights Management")
        == "syntheticmediaversioncontrolrightsmanagement"
    )
    assert to_hashtag("AI-Powered Supply Chain Prediction") == "aipoweredsupplychainprediction"


def test_to_hashtag_keeps_digits():
    assert to_hashtag("Web3 Tools") == "web3tools"


def test_to_hashtag_empty_input_returns_empty():
    assert to_hashtag("") == ""
    assert to_hashtag("&&&") == ""


# --- redact_token: mascara segredos antes de logar (vazamento visto em
# --- producao em 2026-07-06: str(HTTPStatusError) inclui a URL com ?token=...)


def test_redact_token_masks_apify_token():
    msg = (
        "Client error '400 Bad Request' for url "
        "'https://api.apify.com/v2/acts/x~y/run-sync-get-dataset-items?token=apify_api_AbC123'"
    )
    redacted = redact_token(msg)

    assert "apify_api_AbC123" not in redacted
    assert "token=***" in redacted
    # O resto da mensagem sobrevive (o log continua util pra debug).
    assert "400 Bad Request" in redacted
    assert "run-sync-get-dataset-items" in redacted


def test_redact_token_stops_at_next_query_param():
    assert redact_token("?token=secret123&clean=1") == "?token=***&clean=1"


def test_redact_token_without_token_is_unchanged():
    assert redact_token("plain error message") == "plain error message"
