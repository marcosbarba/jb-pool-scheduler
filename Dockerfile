FROM python:3.12-slim-bookworm

# Instalar dependencias del sistema operativo (cron y utilidades de zona horaria)
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv desde su imagen oficial
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /root/.local/bin/
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# 1. Copiar manifiestos y asegurar existencia de README.md
COPY pyproject.toml uv.lock* README.md* ./
RUN touch README.md && uv sync --no-dev --no-install-project

# 2. Copiar el código fuente y scripts
COPY src/ src/
COPY crontab.txt entrypoint.sh ./

# 3. Sincronizar el paquete del proyecto e instalarlo en el entorno
RUN uv sync --no-dev

# Permisos de ejecución
RUN chmod +x entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]