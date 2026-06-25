"""Acesso ao perfil do fundador no banco (registro unico, id=1).

Semeia o perfil a partir do default na primeira leitura, para que o
sistema sempre tenha um perfil valido.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from core.founder_profile import default_profile_dict
from core.logging_config import get_logger
from models import FounderProfile

log = get_logger("founder_profile_service")

_FIELDS = (
    "name",
    "current_country",
    "active_markets",
    "technical_skills",
    "business_skills",
    "target_business_type",
    "tools_available",
    "active_projects",
    "budget_range",
    "avoid",
    "languages",
)


async def get_profile(session: AsyncSession) -> FounderProfile:
    """Retorna o perfil (id=1), semeando do default se ainda nao existir."""
    profile = await session.get(FounderProfile, 1)
    if profile is None:
        profile = FounderProfile(id=1, **default_profile_dict())
        session.add(profile)
        await session.flush()
        log.info("founder_profile.seeded")
    return profile


async def save_profile(session: AsyncSession, data: dict) -> FounderProfile:
    """Cria/atualiza o perfil unico com os campos fornecidos."""
    profile = await session.get(FounderProfile, 1)
    if profile is None:
        profile = FounderProfile(id=1)
        session.add(profile)
    for field in _FIELDS:
        if field in data:
            setattr(profile, field, data[field])
    await session.flush()
    log.info("founder_profile.saved")
    return profile


def profile_to_dict(profile: FounderProfile) -> dict:
    """Converte o modelo para dict (formato usado pela API e pelos agentes)."""
    return {
        "name": profile.name,
        "current_country": profile.current_country,
        "active_markets": profile.active_markets or [],
        "technical_skills": profile.technical_skills or [],
        "business_skills": profile.business_skills or [],
        "target_business_type": profile.target_business_type or [],
        "tools_available": profile.tools_available or [],
        "active_projects": profile.active_projects or "",
        "budget_range": profile.budget_range,
        "avoid": profile.avoid or [],
        "languages": profile.languages or [],
    }
