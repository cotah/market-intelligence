"""Schemas Pydantic para as respostas da API."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from models.opportunity import OpportunityStatus


class OpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    summary: str
    topic_origin: str
    source: str
    status: OpportunityStatus
    discard_reason: str | None
    discarded_by: str | None
    failed_agents: list | None

    trend_data: dict | None
    problem_data: dict | None
    competitor_data: dict | None
    market_data: dict | None
    ai_opportunity_data: dict | None
    compatibility_data: dict | None
    monetization_data: dict | None
    score_data: dict | None
    project_plan: dict | None
    devils_advocate_data: dict | None

    score_total: float | None
    created_at: datetime
    updated_at: datetime


class OpportunityListItem(BaseModel):
    """Versao enxuta para listagem."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    topic_origin: str
    status: OpportunityStatus
    score_total: float | None
    discard_reason: str | None
    created_at: datetime


class ResearchOpportunitiesOut(BaseModel):
    """Resposta da ponte Research Agent (n8n): lote de oportunidades.

    Reaproveita OpportunityOut (mesma estrutura que os 11 agentes produzem).
    `mock=True` sinaliza resposta simulada (sem tocar no banco).
    """

    count: int
    mock: bool
    opportunities: list[OpportunityOut]


class DailyReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_date: date
    total_analyzed: int
    promising_count: int
    excellent_count: int
    summary: str
    payload: dict | None
    created_at: datetime


class PipelineStatusOut(BaseModel):
    enabled: bool
    redis_available: bool
    last_run: dict | None = None


class PipelineActionOut(BaseModel):
    ok: bool
    message: str
    task_id: str | None = None


class FounderProfileSchema(BaseModel):
    """Perfil do fundador (usado tanto no GET quanto no PUT)."""

    name: str = ""
    current_country: str = ""
    active_markets: list[str] = Field(default_factory=list)
    technical_skills: list[str] = Field(default_factory=list)
    business_skills: list[str] = Field(default_factory=list)
    target_business_type: list[str] = Field(default_factory=list)
    ai_tools: list[str] = Field(default_factory=list)
    software_tools: list[str] = Field(default_factory=list)
    hardware_tools: list[str] = Field(default_factory=list)
    active_projects: str = ""
    budget_range: str = "bootstrap"
    avoid: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
