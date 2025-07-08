FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
ENV UV_COMPILE_BYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DOCKER_CONTAINER=True
WORKDIR /app

# Install dependencies (intermediate layer caching)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY uv.lock pyproject.toml ./
COPY src/ .
COPY settings.ini .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

EXPOSE 8080
CMD ["uv", "run", "main.py"]
