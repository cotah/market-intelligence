"""Agente 2 - Problem Hunter.

Para um topico vindo do Trend Hunter, busca evidencias de dor real:
Perplexity (Quora, foruns, reviews), Reddit, Instagram, TikTok e reviews
da App Store (app mais relevante via iTunes Search). Depois pede ao LLM
para extrair frases de dor ("I hate", "I wish", "Why doesn't", ...).

As fontes rodam em paralelo (actors do Apify levam 10-45s cada) e cada
uma falha individualmente sem derrubar o agente.

Criterio de descarte: menos de 3 evidencias de dor real -> descarta.
"""

import asyncio
import traceback

from agents.base import AgentResult, BaseAgent, PipelineContext
from core import llm
from core.config import settings
from core.logging_config import get_logger
from integrations import app_reviews, instagram, perplexity, reddit, tiktok

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

        # 1. Coleta de evidencias em paralelo (cada fonte degrada sozinha).
        hashtag = topic.lower().replace(" ", "")
        raw = await asyncio.gather(
            perplexity.search(
                f"What are the most common complaints, frustrations and unmet needs people have about '{topic}'? "
                'Include real phrases users say like "I hate", "I wish", "why doesn\'t", "there should be". '
                "Look at Quora, forums, Amazon reviews, G2 and Trustpilot.",
                focus="user complaints and reviews",
            ),
            reddit.search_reddit(subreddit="all", query=topic),
            instagram.search_hashtag(hashtag),
            tiktok.search_hashtag(hashtag),
            self._fetch_app_reviews(topic),
            return_exceptions=True,
        )
        perplexity_text = self._or_default(raw[0], "", "perplexity")
        reddit_posts = self._or_default(raw[1], [], "reddit")
        instagram_posts = self._or_default(raw[2], [], "instagram")
        tiktok_posts = self._or_default(raw[3], [], "tiktok")
        app_name, reviews = self._or_default(raw[4], ("", []), "app_reviews")

        evidence_block = self._format_evidence(
            perplexity_text, reddit_posts, instagram_posts, tiktok_posts, app_name, reviews
        )

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

List AT MOST 10 pain_phrases (the strongest ones). Keep each phrase short.
Only include pain_phrases that are backed by the discussions above."""

        # max_tokens menor + no maximo 10 frases => JSON curto, que nao estoura
        # o limite e nao quebra no parse.
        try:
            data = await llm.ask_json(prompt, system=_SYSTEM, max_tokens=1500, temperature=0.2)
        except Exception as e:
            # Mesmo se o parse falhar de vez, nao quebramos com erro cru: seguimos
            # com um resultado VAZIO mas valido. Sem evidencias, o criterio normal
            # abaixo descarta com motivo claro ("sem dor real suficiente").
            log.warning(
                "problem_hunter.empty_fallback",
                topic=topic,
                error=str(e),
                traceback=traceback.format_exc(),
            )
            data = {"pain_phrases": [], "problems": [], "sources": [], "has_real_pain": False}

        # Normaliza a forma (o parser pode ter salvo um JSON parcial) e limita as
        # frases de dor a 10, para os agentes seguintes terem shape consistente.
        if not isinstance(data, dict):
            data = {"pain_phrases": [], "problems": [], "sources": [], "has_real_pain": False}
        pain_phrases = data.get("pain_phrases", [])
        if not isinstance(pain_phrases, list):
            pain_phrases = []
        pain_phrases = pain_phrases[:10]
        data["pain_phrases"] = pain_phrases

        evidence_count = len(pain_phrases)
        problems_count = len(data.get("problems", [])) if isinstance(data.get("problems"), list) else 0
        has_real_pain = bool(data.get("has_real_pain"))

        # Log explicito: mostra se o Problem Hunter realmente achou dor, quantas
        # evidencias e quantos problemas, antes de aplicar o criterio de descarte.
        log.info(
            "problem_hunter.extracted",
            topic=topic,
            pain_phrases=evidence_count,
            problems=problems_count,
            has_real_pain=has_real_pain,
            min_required=_MIN_PAIN_EVIDENCES,
            raw_preview=str(data)[:800],
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
    def _or_default(value, default, source: str):
        """Converte excecao de uma fonte em valor default, com aviso."""
        if isinstance(value, BaseException):
            log.warning("problem_hunter.source_failed", source=source, error=str(value))
            return default
        return value

    @staticmethod
    async def _fetch_app_reviews(topic: str) -> tuple[str, list[dict]]:
        """Mapeia topico -> app da App Store e busca as reviews.

        Sem app encontrado -> ("", []) e a fonte e pulada.
        """
        app = await app_reviews.find_app(topic)
        if not app:
            return ("", [])
        reviews = await app_reviews.get_reviews(app["app_id"])
        return (app["name"], reviews)

    @staticmethod
    def _format_evidence(
        perplexity_text: str,
        reddit_posts: list[dict],
        instagram_posts: list[dict],
        tiktok_posts: list[dict],
        app_name: str,
        reviews: list[dict],
    ) -> str:
        parts: list[str] = []

        if perplexity_text:
            parts.append(f"[Perplexity - reviews & forums]\n{perplexity_text}")

        if reddit_posts:
            lines = "\n".join(
                f"- ({p['upvotes']} upvotes) {p['title']}: {p['body']}" for p in reddit_posts
            )
            note = " (MOCK data)" if reddit_posts[0].get("is_mock") else ""
            parts.append(f"[Reddit{note}]\n{lines}")

        if instagram_posts:
            lines = "\n".join(
                f"- ({p['likes']} likes) {p['caption']}" for p in instagram_posts
            )
            note = " (MOCK data)" if instagram_posts[0].get("is_mock") else ""
            parts.append(f"[Instagram{note}]\n{lines}")

        if tiktok_posts:
            lines = "\n".join(
                f"- ({p['likes']} likes) {p['description']}" for p in tiktok_posts
            )
            note = " (MOCK data)" if tiktok_posts[0].get("is_mock") else ""
            parts.append(f"[TikTok{note}]\n{lines}")

        if reviews:
            lines = "\n".join(
                f"- ({r['rating']}/5) {r['title']}: {r['body']}" for r in reviews
            )
            note = " (MOCK data)" if reviews[0].get("is_mock") else ""
            parts.append(f"[App Store reviews - {app_name}{note}]\n{lines}")

        if not parts:
            return "(No discussions found. If you have no evidence of real pain, set has_real_pain to false and return an empty pain_phrases list.)"

        return "\n\n".join(parts)


# Exporto o minimo de evidencias para que os testes possam referenciar.
MIN_PAIN_EVIDENCES = _MIN_PAIN_EVIDENCES
