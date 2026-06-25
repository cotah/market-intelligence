# Imagem de producao do backend (usada no Railway).
# Controle total do build com uv pinado, sem depender do Nixpacks.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# uv pinado na mesma versao do ambiente local (compativel com o uv.lock).
RUN pip install --no-cache-dir uv==0.11.9

# 1) Instala SO as dependencias. Esta camada fica em cache enquanto o
#    pyproject/uv.lock nao mudam. --no-install-project porque o codigo
#    do projeto ainda nao foi copiado.
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

# 2) Copia o codigo e instala o proprio projeto.
COPY . .
RUN uv sync --no-dev --frozen

# Web: roda as migrations e sobe a API.
# IMPORTANTE: a porta vem de $PORT (injetada pelo Railway). Nunca hardcodar.
# Shell-form para o && e a expansao de ${PORT:-8000} funcionarem.
# Os servicos worker e beat sobrescrevem este comando no Railway
# (Custom Start Command). Veja README -> Deploy.
CMD uv run --no-sync alembic upgrade head && uv run --no-sync uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
