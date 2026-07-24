# syntax=docker/dockerfile:1@sha256:87999aa3d42bdc6bea60565083ee17e86d1f3339802f543c0d03998580f9cb89
# hadolint global ignore=DL3008

FROM mitodl/ol-python-base:3.14@sha256:676c985512e6170c63c03f33ac669b9aa1a71901ee1b30c33ff811557099c3c2 AS base
LABEL maintainer="ODL DevOps <mitx-devops@mit.edu>"

# App-specific apt extras; common-core packages (git, curl, libjpeg-dev,
# zlib1g-dev, net-tools, build-essential, libpq-dev, postgresql-client,
# pkg-config, libxmlsec1-dev) are in mitodl/ol-python-base:3.13.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      libmagic1 \
      libxmlsec1-openssl

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
ENV PATH="/opt/venv/bin:$PATH"

# ─── Dependency install ───────────────────────────────────────────────────────
FROM base AS deps

COPY --chown=mitodl:mitodl pyproject.toml uv.lock /src/

USER mitodl
WORKDIR /src
# BuildKit cache mount keeps the uv download cache across builds.
RUN --mount=type=cache,target=/opt/uv-cache,uid=1000,gid=1000 \
    uv sync --frozen --no-install-project --no-dev

# ─── Node / frontend asset build ─────────────────────────────────────────────
FROM node:24-slim@sha256:6f7b03f7c2c8e2e784dcf9295400527b9b1270fd37b7e9a7285cf83b6951452d AS node_builder
COPY . /src
WORKDIR /src
ENV NODE_ENV=production
RUN yarn install --immutable && yarn build

# ─── Code stage ───────────────────────────────────────────────────────────────
FROM deps AS code

COPY --chown=mitodl:mitodl . /src
WORKDIR /src

# ─── Runtime target ───────────────────────────────────────────────────────────
FROM code AS runtime

EXPOSE 8043
ENV PORT=8043
CMD ["sh", "-c", "exec granian --interface wsgi --host 0.0.0.0 --port ${PORT:-8043} --workers 2 main.wsgi:application"]

# ─── Production target ────────────────────────────────────────────────────────
FROM runtime AS production

COPY --from=node_builder --chown=mitodl:mitodl /src/static /src/static
COPY --from=node_builder --chown=mitodl:mitodl /src/webpack-stats.json /src/webpack-stats.json

ARG GIT_REF
RUN echo "$GIT_REF" >> /src/static/hash.txt

# ─── Development target ───────────────────────────────────────────────────────
FROM runtime AS development

RUN --mount=type=cache,target=/opt/uv-cache,uid=1000,gid=1000 \
    uv sync --frozen --no-install-project
