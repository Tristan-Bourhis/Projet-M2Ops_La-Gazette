# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.lock ./
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.lock
COPY pyproject.toml ./
COPY src ./src
RUN /opt/venv/bin/pip install --no-deps .

FROM python:3.12-slim-bookworm AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --gid 10001 gazette && useradd --uid 10001 --gid gazette --no-create-home gazette \
    && mkdir -p /app /data && chown gazette:gazette /data
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY sources.csv ./
COPY tests/fixtures/ouest-france.xml ./tests/fixtures/ouest-france.xml
USER 10001:10001
CMD ["python", "-m", "gazette"]

FROM runtime AS test
USER root
COPY requirements-dev.lock ./
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements-dev.lock
COPY pyproject.toml ./
COPY src ./src
COPY tests ./tests
COPY bin/check ./bin/check
USER 10001:10001
CMD ["sh", "bin/check"]

# Le build sans --target produit toujours l'image minimale de production.
FROM runtime AS final
