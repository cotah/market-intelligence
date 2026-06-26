"""Condensa textos longos de pesquisa antes de irem para os agentes.

Em vez de truncar o texto cru (que perde informacao no meio), pedimos ao
Claude um resumo denso, so com o que importa para a pipeline. Assim os
agentes recebem informacao densa e relevante em vez de texto bruto longo,
e os prompts ficam pequenos (evita o 400 do Claude por excesso de conteudo).

Degrada graciosamente: se o resumo falhar, cai para o texto cru cortado.
"""

from core import llm
from core.logging_config import get_logger

log = get_logger("summarize")

# Acima deste tamanho vale a pena resumir; abaixo, o texto ja e denso.
_CONDENSE_THRESHOLD = 2000
# Teto do que mandamos ao sumarizador, para a propria chamada nao estourar.
_MAX_INPUT_CHARS = 16000

_PROMPT = """Você é um assistente de pesquisa de mercado. Resuma o texto abaixo em no máximo 800 palavras, mantendo apenas:
- tendências de mercado relevantes
- problemas reais que pessoas enfrentam
- dados de tamanho de mercado
- nomes de empresas/produtos relevantes
- frases que indicam dor do usuário (I hate, I wish, Why doesn't, etc)
Descarte opiniões genéricas, repetições e conteúdo irrelevante.

Texto: {text}"""

_SYSTEM = "Você resume pesquisas de mercado de forma densa, factual e em português."


async def condense(text: str, *, source: str = "") -> str:
    """Resume `text` se ele passar do limite; senao devolve como veio.

    `source` e so para o log (perplexity/serper/grok).
    """
    if not text or len(text) <= _CONDENSE_THRESHOLD:
        return text

    clipped = text[:_MAX_INPUT_CHARS]
    try:
        # cap_chars=None: o sumarizador precisa ver o texto inteiro; o cap de
        # prompt dos agentes nao se aplica aqui.
        summary = await llm.ask(
            _PROMPT.format(text=clipped),
            system=_SYSTEM,
            max_tokens=1200,
            temperature=0.2,
            cap_chars=None,
        )
        summary = summary.strip()
        log.info(
            "summarize.condensed",
            source=source,
            original_chars=len(text),
            summary_chars=len(summary),
        )
        return summary or clipped
    except Exception as e:  # noqa: BLE001 - degradacao graciosa
        log.warning("summarize.failed", source=source, error=str(e))
        return clipped
