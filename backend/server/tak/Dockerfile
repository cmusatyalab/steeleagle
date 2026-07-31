FROM ghcr.io/astral-sh/uv:debian-slim

WORKDIR /app

COPY . /app

RUN uv sync --python 3.11

CMD ["uv", "run", "steeleagle-tak"]
