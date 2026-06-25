"""Wrapper de LLM: tenta Claude primeiro, cai para OpenAI se falhar.

Se ambos falharem (ou nao houver chave configurada), lanca LLMException
com mensagem clara. Os agentes dependem deste modulo para qualquer
raciocinio que envolva texto livre.
"""

import json
import re
from typing import Any

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from core.config import settings
from core.exceptions import LLMException
from core.logging_config import get_logger

log = get_logger("llm")

# Clientes criados sob demanda (lazy) para nao quebrar se a chave faltar.
_anthropic: AsyncAnthropic | None = None
_openai: AsyncOpenAI | None = None


def _get_anthropic() -> AsyncAnthropic | None:
    global _anthropic
    if not settings.anthropic_api_key:
        return None
    if _anthropic is None:
        _anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _anthropic


def _get_openai() -> AsyncOpenAI | None:
    global _openai
    if not settings.openai_api_key:
        return None
    if _openai is None:
        _openai = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai


async def _ask_anthropic(prompt: str, system: str, max_tokens: int, temperature: float) -> str:
    client = _get_anthropic()
    if client is None:
        raise LLMException("ANTHROPIC_API_KEY ausente")
    resp = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system or "You are a helpful business analyst.",
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def _is_modern_openai(model: str) -> bool:
    """gpt-5.x e modelos de raciocinio (o1/o3/o4) usam max_completion_tokens
    e so aceitam temperatura padrao (=1), diferente dos gpt-4.x."""
    m = model.lower()
    return m.startswith(("gpt-5", "o1", "o3", "o4"))


async def _ask_openai(prompt: str, system: str, max_tokens: int, temperature: float) -> str:
    client = _get_openai()
    if client is None:
        raise LLMException("OPENAI_API_KEY ausente")
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    model = settings.openai_model
    kwargs: dict = {"model": model, "messages": messages}
    if _is_modern_openai(model):
        # Modelos novos: usam max_completion_tokens e temperatura padrao.
        # Damos folga ao limite porque parte dos tokens vai para raciocinio.
        kwargs["max_completion_tokens"] = max(max_tokens, 4000)
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = temperature

    resp = await client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


async def ask(
    prompt: str,
    system: str = "",
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> str:
    """Pergunta ao LLM. Claude primeiro; OpenAI como fallback.

    Lanca LLMException se ambos falharem.
    """
    try:
        result = await _ask_anthropic(prompt, system, max_tokens, temperature)
        log.info("llm.answered", provider="anthropic")
        return result
    except Exception as anthropic_err:  # noqa: BLE001 - queremos cair para o fallback
        log.warning("llm.anthropic_failed", error=str(anthropic_err))
        try:
            result = await _ask_openai(prompt, system, max_tokens, temperature)
            log.info("llm.answered", provider="openai")
            return result
        except Exception as openai_err:  # noqa: BLE001
            log.error("llm.all_failed", anthropic_error=str(anthropic_err), openai_error=str(openai_err))
            raise LLMException(
                f"Claude e OpenAI falharam. Claude: {anthropic_err} | OpenAI: {openai_err}"
            ) from openai_err


def _extract_json(text: str) -> Any:
    """Extrai o primeiro objeto/array JSON de um texto de LLM.

    Lida com blocos ```json ... ``` e com texto extra antes/depois.
    """
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidate = fence.group(1).strip() if fence else text.strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Fallback: pega do primeiro { ou [ ate o ultimo } ou ]
    start = min((i for i in (candidate.find("{"), candidate.find("[")) if i != -1), default=-1)
    end = max(candidate.rfind("}"), candidate.rfind("]"))
    if start != -1 and end != -1 and end > start:
        return json.loads(candidate[start : end + 1])

    raise LLMException(f"Resposta do LLM nao continha JSON valido: {text[:200]}")


async def ask_json(
    prompt: str,
    system: str = "",
    max_tokens: int = 2000,
    temperature: float = 0.2,
) -> Any:
    """Igual ao `ask`, mas espera e faz parse de JSON na resposta."""
    full_system = (
        system + "\n\nResponda APENAS com JSON valido, sem texto extra."
    ).strip()
    raw = await ask(prompt, system=full_system, max_tokens=max_tokens, temperature=temperature)
    return _extract_json(raw)
