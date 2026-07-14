"""Perfil do fundador persistido no banco (1 registro POR conta).

Editavel pela tela /profile do frontend. O Agente 6 carrega este perfil
em vez do hardcoded, para refletir mudancas de pais, mercados e skills.

Multi-tenancy: a PK e o account_id — cada cliente tem o proprio perfil,
semeado do default no primeiro acesso (core/founder_profile_service.py).
"""

from datetime import datetime
import uuid

from sqlalchemy import String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class FounderProfile(Base):
    __tablename__ = "founder_profile"

    # PK = conta dona do perfil (1 perfil por conta).
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    name: Mapped[str] = mapped_column(String(200), default="")
    current_country: Mapped[str] = mapped_column(String(200), default="")
    active_markets: Mapped[list] = mapped_column(JSONB, default=list)
    technical_skills: Mapped[list] = mapped_column(JSONB, default=list)
    business_skills: Mapped[list] = mapped_column(JSONB, default=list)
    target_business_type: Mapped[list] = mapped_column(JSONB, default=list)

    # Ferramentas separadas por categoria (contexto mais rico para o Agente 6).
    ai_tools: Mapped[list] = mapped_column(JSONB, default=list)
    software_tools: Mapped[list] = mapped_column(JSONB, default=list)
    hardware_tools: Mapped[list] = mapped_column(JSONB, default=list)

    # Legado: mantido por compatibilidade (coluna ja existente no banco).
    # Nao e mais exposto na API/UI; substituido por ai/software/hardware_tools.
    tools_available: Mapped[list] = mapped_column(JSONB, default=list)

    active_projects: Mapped[str] = mapped_column(Text, default="")
    budget_range: Mapped[str] = mapped_column(String(50), default="bootstrap")
    avoid: Mapped[list] = mapped_column(JSONB, default=list)
    languages: Mapped[list] = mapped_column(JSONB, default=list)

    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<FounderProfile name={self.name!r} country={self.current_country!r}>"
