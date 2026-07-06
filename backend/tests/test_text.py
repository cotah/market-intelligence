"""Testes do helper de texto compartilhado (core/text.py).

to_hashtag: transforma texto livre em hashtag valida (lowercase, so
alfanumerico). Criado apos a validacao real de 2026-07-06, quando
hashtags derivadas de topicos com "&" e hifens quebravam os atores
de Instagram/TikTok na Apify.
"""

from core.text import to_hashtag


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
