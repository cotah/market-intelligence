"""Wrapper de LLM: tenta Claude primeiro, cai para OpenAI se falhar.

Se ambos falharem (ou nao houver chave configurada), lanca LLMException
com mensagem clara. Os agentes dependem deste modulo para qualquer
raciocinio que envolva texto livre.
"""

import json
import re
import traceback
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

# Em um 400 do Claude (prompt grande demais), tentamos de novo com o prompt
# cortado a este tamanho antes de cair para a OpenAI.
_MAX_RETRY_PROMPT_CHARS = 3000


def _is_bad_request(err: Exception) -> bool:
    """True se o erro do Claude for um HTTP 400 (Bad Request).

    O SDK da Anthropic expoe `status_code` nas excecoes de API; usamos isso
    como sinal primario e caimos para uma checagem textual por seguranca.
    """
    if getattr(err, "status_code", None) == 400:
        return True
    text = str(err).lower()
    return "400" in text and "bad request" in text


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

        # 400 do Claude costuma ser prompt+contexto grande demais. Antes de cair
        # para a OpenAI, tentamos UMA vez com o prompt cortado nos primeiros
        # _MAX_RETRY_PROMPT_CHARS chars.
        if _is_bad_request(anthropic_err) and len(prompt) > _MAX_RETRY_PROMPT_CHARS:
            truncated = prompt[:_MAX_RETRY_PROMPT_CHARS]
            log.warning(
                "llm.anthropic_retry_truncated",
                original_chars=len(prompt),
                truncated_chars=len(truncated),
            )
            try:
                result = await _ask_anthropic(truncated, system, max_tokens, temperature)
                log.info("llm.answered", provider="anthropic", truncated=True)
                return result
            except Exception as retry_err:  # noqa: BLE001 - segue para o fallback
                log.warning("llm.anthropic_retry_failed", error=str(retry_err))

        try:
            result = await _ask_openai(prompt, system, max_tokens, temperature)
            log.info("llm.answered", provider="openai")
            return result
        except Exception as openai_err:  # noqa: BLE001
            log.error(
                "llm.all_failed",
                anthropic_error=str(anthropic_err),
                openai_error=str(openai_err),
                traceback=traceback.format_exc(),
            )
            raise LLMException(
                f"Claude e OpenAI falharam. Claude: {anthropic_err} | OpenAI: {openai_err}"
            ) from openai_err


def _repair_truncated_json(s: str) -> str | None:
    """Repara um JSON truncado (cortado no meio pelo max_tokens) fechando as
    estruturas abertas.

    Caminha o texto rastreando aspas e a pilha de colchetes/chaves e guarda o
    ultimo ponto SEGURO: logo apos um delimitador ',' '}' ']', onde o elemento
    anterior ja esta completo. No fim, corta nesse ponto e fecha o que ficou
    aberto, salvando os itens que vieram inteiros. Retorna a string reparada
    ou None se nao houver nada salvavel.
    """
    stack: list[str] = []
    in_string = False
    escape = False
    safe_cut: int | None = None
    safe_stack: tuple[str, ...] = ()

    for i, ch in enumerate(s):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if not stack:
                return None
            stack.pop()
            safe_cut, safe_stack = i + 1, tuple(stack)
        elif ch == ",":
            safe_cut, safe_stack = i, tuple(stack)

    if safe_cut is None:
        return None
    repaired = s[:safe_cut].rstrip().rstrip(",").rstrip()
    return repaired + "".join(reversed(safe_stack))


def _extract_json(text: str) -> Any:
    """Extrai o primeiro objeto/array JSON de um texto de LLM.

    Lida com blocos ```json ... ``` e com texto extra antes/depois. Se a
    resposta veio truncada (max_tokens), tenta salvar o maior prefixo valido.
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
        try:
            return json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            pass

    # Ultima tentativa: JSON truncado no meio (resposta cortada pelo max_tokens).
    # Recupera o maior prefixo valido fechando as estruturas abertas.
    if start != -1:
        repaired = _repair_truncated_json(candidate[start:])
        if repaired is not None:
            try:
                data = json.loads(repaired)
                log.warning(
                    "llm.json.repaired",
                    reason="resposta provavelmente truncada pelo max_tokens",
                    original_chars=len(candidate),
                    repaired_chars=len(repaired),
                )
                return data
            except json.JSONDecodeError:
                pass

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
    # Loga o que o LLM realmente devolveu ANTES do parse: se o parse falhar,
    # ja temos o preview aqui (e o agente loga o traceback). Isto e o ponto
    # cego que escondia "API chamada com sucesso mas nada salvo".
    log.info("llm.json.raw", chars=len(raw), preview=raw[:500])
    data = _extract_json(raw)
    log.info(
        "llm.json.parsed",
        kind=type(data).__name__,
        keys=list(data.keys()) if isinstance(data, dict) else None,
        length=len(data) if isinstance(data, list) else None,
    )
    return data
