FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

WORKDIR /app

# Dependencies first, so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock ./
ENV UV_COMPILE_BYTECODE=1
RUN uv sync --frozen --no-dev

COPY app ./app

RUN useradd --create-home appuser
USER appuser

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
