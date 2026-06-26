"""Testes do condensador de pesquisa (sem rede: LLM mockado)."""

from core import summarize


async def test_condense_short_text_passes_through(monkeypatch):
    # Texto curto nao deve nem chamar o LLM.
    called = False

    async def fake_ask(*args, **kwargs):
        nonlocal called
        called = True
        return "nao deveria ser chamado"

    monkeypatch.setattr(summarize.llm, "ask", fake_ask)

    text = "texto curto e denso"
    assert await summarize.condense(text) == text
    assert called is False


async def test_condense_long_text_calls_llm(monkeypatch):
    async def fake_ask(*args, **kwargs):
        return "RESUMO DENSO"

    monkeypatch.setattr(summarize.llm, "ask", fake_ask)

    long_text = "x" * 5000
    assert await summarize.condense(long_text) == "RESUMO DENSO"


async def test_condense_falls_back_to_clipped_on_error(monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(summarize.llm, "ask", boom)

    long_text = "y" * 5000
    result = await summarize.condense(long_text)
    # Degrada gracioso: volta o texto cru cortado, sem quebrar.
    assert result == long_text[: summarize._MAX_INPUT_CHARS]
