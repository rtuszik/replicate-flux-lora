# FROM python:3.12-slim
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DOCKER_CONTAINER=True

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY src/ .
COPY settings.ini .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

EXPOSE 8080

CMD ["uv", "run", "main.py"]
