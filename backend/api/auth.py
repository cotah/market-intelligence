"""Autenticacao dos endpoints de CONTROLE.

Endpoints que gastam creditos de LLM ou alteram estado (ligar/desligar
pipeline, rodada avulsa, editar perfil, gerar relatorio) exigem a chave
CONTROL_API_KEY via header X-API-Key — mesmo padrao da Research API
(api/research.py):

- secrets.compare_digest (timing-safe); a chave NUNCA aparece em logs.
- Fail closed: sem chave configurada no ambiente => 503.
- Contrato: 401 sem header | 403 chave errada | 503 nao configurado.

O frontend NAO conhece essa chave: ele chama um proxy server-side no
Next.js (/api/control/...) que injeta o header. Assim a chave nunca
chega ao navegador.
"""

import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from core.config import settings
from core.logging_config import get_logger

log = get_logger("api.auth")

# auto_error=False para controlarmos os codigos (401 vs 403) manualmente.
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_control_key(api_key: str | None = Security(_api_key_header)) -> None:
    """Valida a chave dos endpoints de controle. Nunca loga o valor recebido."""
    if not settings.control_api_key:
        # Fail closed: sem chave configurada no ambiente, controle desligado.
        log.warning("control.auth.not_configured")
        raise HTTPException(status_code=503, detail="Control endpoints not configured")
    if not api_key:
        log.warning("control.auth.missing_key")
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if not secrets.compare_digest(api_key, settings.control_api_key):
        log.warning("control.auth.invalid_key")
        raise HTTPException(status_code=403, detail="Invalid API key")


async def require_read_key(api_key: str | None = Security(_api_key_header)) -> None:
    """Valida a chave dos endpoints de LEITURA (dados de negocio + perfil).

    Mesmo contrato de require_control_key, porem com chave DEDICADA
    (settings.read_api_key). Fecha o backend apos o achado I-1: as leituras
    deixam de ser publicas. Nunca loga o valor recebido.
    """
    if not settings.read_api_key:
        # Fail closed: sem chave configurada, leitura desligada.
        log.warning("api.auth.read.not_configured")
        raise HTTPException(status_code=503, detail="Read endpoints not configured")
    if not api_key:
        log.warning("api.auth.read.missing_key")
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if not secrets.compare_digest(api_key, settings.read_api_key):
        log.warning("api.auth.read.invalid_key")
        raise HTTPException(status_code=403, detail="Invalid API key")
