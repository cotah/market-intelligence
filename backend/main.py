"""Entry point da API FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.research import router as research_router
from api.routes import router
from core.config import settings
from core.logging_config import configure_logging, get_logger

configure_logging()
log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("app.startup", environment=settings.environment)
    yield
    log.info("app.shutdown")


app = FastAPI(
    title="Market Intelligence AI",
    description="Pipeline de 11 agentes que cacam oportunidades de negocio.",
    version="0.1.0",
    lifespan=lifespan,
)

# Origens permitidas: em dev (ALLOWED_ORIGINS vazio) libera tudo ['*'];
# em producao, setar ALLOWED_ORIGINS=https://seu-app.vercel.app no Railway.
_origins = settings.allowed_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # allow_credentials nao pode ser True junto com '*' (regra do navegador).
    # A API nao usa cookies/sessao, entao isto e seguro.
    allow_credentials=_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
log.info("cors.configured", allowed_origins=_origins)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "service": "market-intelligence", "environment": settings.environment}


app.include_router(router)
app.include_router(research_router)
