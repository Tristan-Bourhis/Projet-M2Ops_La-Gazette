# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
# Compilateur : hdbscan n'a pas de paquet précompilé pour toutes les architectures (ARM).
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.lock ./
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.lock
# Modèle d'embedding intégré à l'image, à la révision de config/clustering.yaml :
# version connue et tracée, aucun téléchargement pendant les runs.
COPY config ./config
ENV HF_HOME=/opt/hf
RUN /opt/venv/bin/python -c "import yaml; from sentence_transformers import SentenceTransformer; \
m = yaml.safe_load(open('config/clustering.yaml'))['modele']; \
SentenceTransformer(m['nom'], revision=m['revision'], device='cpu')"
COPY pyproject.toml ./
COPY src ./src
RUN /opt/venv/bin/pip install --no-deps .

FROM python:3.12-slim-bookworm AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# Conteneur en lecture seule : modèle hors ligne, caches de numba (UMAP) et matplotlib dans /tmp.
ENV HF_HOME=/opt/hf HF_HUB_OFFLINE=1 NUMBA_CACHE_DIR=/tmp/numba MPLCONFIGDIR=/tmp/matplotlib
RUN groupadd --gid 10001 gazette && useradd --uid 10001 --gid gazette --no-create-home gazette \
    && mkdir -p /app /data && chown gazette:gazette /data
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/hf /opt/hf
COPY sources.csv ./
COPY config ./config
COPY migrations ./migrations
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
