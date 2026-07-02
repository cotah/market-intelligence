"""Testes do fluxo do `ask()`: Claude -> retry truncado no 400 -> OpenAI.

Mocka _ask_anthropic/_ask_openai (sem rede) para fixar a ordem de fallback
e o comportamento do cap de prompt (_cap_prompt).
"""

import pytest

import core.llm as llm
from core.exceptions import LLMException


class Bad400(Exception):
    status_code = 400


def _record(calls, name, response=None, error=None):
    async def fake(prompt, system, max_tokens, temperature):
        calls.append({"provider": name, "prompt": prompt})
        if error is not None:
            raise error
        return response

    return fake


# ------------------------------ Ordem de fallback ------------------------------
async def test_ask_uses_anthropic_first_and_skips_openai(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(llm, "_ask_anthropic", _record(calls, "anthropic", "ok claude"))
    monkeypatch.setattr(llm, "_ask_openai", _record(calls, "openai", "ok openai"))

    assert await llm.ask("hello") == "ok claude"
    assert [c["provider"] for c in calls] == ["anthropic"]


async def test_ask_400_retries_anthropic_with_truncated_prompt(monkeypatch):
    calls: list[dict] = []
    attempts = {"n": 0}

    async def anthropic(prompt, system, max_tokens, temperature):
        attempts["n"] += 1
        calls.append({"provider": "anthropic", "prompt": prompt})
        if attempts["n"] == 1:
            raise Bad400("too long")
        return "ok truncated"

    monkeypatch.setattr(llm, "_ask_anthropic", anthropic)
    monkeypatch.setattr(llm, "_ask_openai", _record(calls, "openai", "ok openai"))

    big_prompt = "x" * 3000  # > _MAX_RETRY_PROMPT_CHARS, < cap default
    assert await llm.ask(big_prompt) == "ok truncated"
    # 2 tentativas no Claude, nenhuma na OpenAI.
    assert [c["provider"] for c in calls] == ["anthropic", "anthropic"]
    # O retry foi com prompt cortado ao limite agressivo.
    assert len(calls[1]["prompt"]) <= llm._MAX_RETRY_PROMPT_CHARS + len(
        "\n...[conteudo cortado]...\n"
    )


async def test_ask_400_with_retry_failure_falls_back_to_openai(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(llm, "_ask_anthropic", _record(calls, "anthropic", error=Bad400("nope")))
    monkeypatch.setattr(llm, "_ask_openai", _record(calls, "openai", "ok openai"))

    assert await llm.ask("x" * 3000) == "ok openai"
    # Claude original + retry truncado + fallback OpenAI.
    assert [c["provider"] for c in calls] == ["anthropic", "anthropic", "openai"]


async def test_ask_non_400_error_goes_straight_to_openai(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(
        llm, "_ask_anthropic", _record(calls, "anthropic", error=RuntimeError("timeout"))
    )
    monkeypatch.setattr(llm, "_ask_openai", _record(calls, "openai", "ok openai"))

    assert await llm.ask("x" * 3000) == "ok openai"
    # Sem retry truncado: erro nao-400 cai direto para o fallback.
    assert [c["provider"] for c in calls] == ["anthropic", "openai"]


async def test_ask_raises_llmexception_with_both_errors(monkeypatch):
    monkeypatch.setattr(
        llm, "_ask_anthropic", _record([], "anthropic", error=RuntimeError("claude caiu"))
    )
    monkeypatch.setattr(
        llm, "_ask_openai", _record([], "openai", error=RuntimeError("openai caiu"))
    )

    with pytest.raises(LLMException) as exc:
        await llm.ask("hello")
    assert "claude caiu" in str(exc.value)
    assert "openai caiu" in str(exc.value)


# --------------------------------- Cap de prompt ---------------------------------
def test_cap_prompt_keeps_short_prompt_intact():
    assert llm._cap_prompt("curto", 100) == "curto"


def test_cap_prompt_preserves_head_and_tail():
    prompt = "INICIO" + "m" * 10000 + "FIM"
    capped = llm._cap_prompt(prompt, 1000)

    assert capped.startswith("INICIO")
    assert capped.endswith("FIM")
    assert "[conteudo cortado]" in capped
    assert len(capped) <= 1000 + len("\n...[conteudo cortado]...\n")


async def test_ask_caps_prompt_proactively_by_default(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(llm, "_ask_anthropic", _record(calls, "anthropic", "ok"))

    await llm.ask("z" * 10000)  # acima do cap default de 4000

    sent = calls[0]["prompt"]
    assert len(sent) <= llm._MAX_PROMPT_CHARS + len("\n...[conteudo cortado]...\n")


async def test_ask_with_cap_none_sends_full_prompt(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(llm, "_ask_anthropic", _record(calls, "anthropic", "ok"))

    await llm.ask("z" * 10000, cap_chars=None)  # ex.: sumarizador

    assert len(calls[0]["prompt"]) == 10000
