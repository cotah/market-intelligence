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

# Entrypoint com logs explicitos: roda as migrations e sobe a API.
# Se o alembic falhar, o 'set -e' derruba o container com erro visivel
# (em vez de seguir silenciosamente e dar 502). A porta vem de $PORT.
# Os servicos worker e beat sobrescrevem o comando no Railway (Custom Start
# Command). Veja README -> Deploy.
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh
CMD ["./entrypoint.sh"]
