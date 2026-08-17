FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY backend ./backend
COPY workers ./workers

RUN uv sync --frozen

EXPOSE 8000
# RNF-001: un unico proceso/event loop no alcanzaba el p95<=500ms bajo
# carga de referencia (medido con tests/load/k6-crud.js) - GET /health/ready
# daba p95=579ms pese a ser la ruta mas barata (SELECT 1 + Redis PING),
# indicio de contencion compartida, no de un endpoint lento en particular.
# 2 workers reparte esa carga entre 2 procesos/event loops sin multiplicar
# demasiado las conexiones a Postgres (ver pool_size en app/db/session.py,
# ya calculado contra esto).
CMD ["uv", "run", "--package", "backend", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
