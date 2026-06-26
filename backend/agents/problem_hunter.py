"""Agente 2 - Problem Hunter.

Para um topico vindo do Trend Hunter, busca evidencias de dor real:
Perplexity (Quora, foruns, reviews) + Reddit (mock). Depois pede ao LLM
para extrair frases de dor ("I hate", "I wish", "Why doesn't", ...).

Criterio de descarte: menos de 3 evidencias de dor real -> descarta.
"""

from agents.base import AgentResult, BaseAgent, PipelineContext
from core import llm
from core.config import settings
from core.logging_config import get_logger
from integrations import perplexity, reddit

log = get_logger("agents.problem_hunter")

_MIN_PAIN_EVIDENCES = 3

_SYSTEM = (
    "You analyze user discussions to find REAL pain points behind a topic. "
    "You only report pains that have concrete evidence (a quote or paraphrase "
    "from a real complaint). Do not invent pains."
)


class ProblemHunterAgent(BaseAgent):
    name = "problem_hunter"

    async def run(self, context: PipelineContext) -> AgentResult:
        topic = context.topic
        log.info("problem_hunter.started", topic=topic)

        # 1. Coleta de evidencias (degrada graciosamente).
        perplexity_text = await perplexity.search(
            f"What are the most common complaints, frustrations and unmet needs people have about '{topic}'? "
            'Include real phrases users say like "I hate", "I wish", "why doesn\'t", "there should be". '
            "Look at Quora, forums, Amazon reviews, G2 and Trustpilot.",
            focus="user complaints and reviews",
        )
        reddit_posts = await reddit.search_reddit(subreddit="all", query=topic)

        evidence_block = self._format_evidence(perplexity_text, reddit_posts)

        # 2. Extracao de dores via LLM.
        prompt = f"""Topic: "{topic}"

Based on the user discussions below, extract the REAL pain points.

DISCUSSIONS:
{evidence_block}

Return a JSON object with this exact shape:
{{
  "pain_phrases": ["actual or paraphrased user complaint", ...],
  "problems": [
    {{"problem": "short description", "severity": "high|medium|low", "evidence": "the quote"}}
  ],
  "sources": ["Reddit (mock)", "Perplexity", ...],
  "has_real_pain": true
}}

Only include pain_phrases that are backed by the discussions above."""

        try:
            data = await llm.ask_json(prompt, system=_SYSTEM, max_tokens=1800, temperature=0.2)
        except Exception as e:
            # Falha de LLM nao deve derrubar a pipeline inteira: descartamos com motivo.
            log.error("problem_hunter.failed", topic=topic, error=str(e))
            return AgentResult(
                success=False,
                should_discard=True,
                discard_reason=f"Problem Hunter falhou ao analisar dores: {e}",
                error=str(e),
            )

        pain_phrases = data.get("pain_phrases", []) if isinstance(data, dict) else []
        evidence_count = len(pain_phrases)
        problems_count = len(data.get("problems", [])) if isinstance(data, dict) else 0
        has_real_pain = bool(data.get("has_real_pain")) if isinstance(data, dict) else False

        # Log explicito: mostra se o Problem Hunter realmente achou dor, quantas
        # evidencias e quantos problemas, antes de aplicar o criterio de descarte.
        log.info(
            "problem_hunter.extracted",
            topic=topic,
            pain_phrases=evidence_count,
            problems=problems_count,
            has_real_pain=has_real_pain,
            min_required=_MIN_PAIN_EVIDENCES,
        )

        # 3. Criterio de descarte.
        if evidence_count < _MIN_PAIN_EVIDENCES:
            reason = (
                f"Sem dor real suficiente: {evidence_count} evidencia(s) "
                f"(minimo {_MIN_PAIN_EVIDENCES})."
            )
            log.info("problem_hunter.discarded", topic=topic, evidence_count=evidence_count)
            return AgentResult(
                success=True,
                data=data,
                should_discard=True,
                discard_reason=reason,
            )

        log.info("problem_hunter.completed", topic=topic, evidence_count=evidence_count)
        return AgentResult(success=True, data=data)

    @staticmethod
    def _format_evidence(perplexity_text: str, reddit_posts: list[dict]) -> str:
        parts: list[str] = []

        if perplexity_text:
            parts.append(f"[Perplexity - reviews & forums]\n{perplexity_text}")

        if reddit_posts:
            lines = "\n".join(
                f"- ({p['upvotes']} upvotes) {p['title']}: {p['body']}" for p in reddit_posts
            )
            note = " (MOCK data)" if reddit_posts and reddit_posts[0].get("is_mock") else ""
            parts.append(f"[Reddit{note}]\n{lines}")

        if not parts:
            return "(No discussions found. If you have no evidence of real pain, set has_real_pain to false and return an empty pain_phrases list.)"

        return "\n\n".join(parts)


# Exporto o minimo de evidencias para que os testes possam referenciar.
MIN_PAIN_EVIDENCES = _MIN_PAIN_EVIDENCES
