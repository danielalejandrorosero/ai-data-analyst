FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY backend ./backend
COPY workers ./workers

RUN uv sync --frozen

CMD ["uv", "run", "--package", "workers", "arq", "tasks.worker_settings.WorkerSettings"]
