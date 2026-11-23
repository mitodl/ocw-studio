# syntax=docker/dockerfile:1
# hadolint global ignore=DL3008

FROM mitodl/ol-python-base:3.14 AS base
LABEL maintainer="ODL DevOps <mitx-devops@mit.edu>"

# App-specific apt extras; common-core packages (git, curl, libjpeg-dev,
# zlib1g-dev, net-tools, build-essential, libpq-dev, postgresql-client,
# pkg-config, libxmlsec1-dev) are in mitodl/ol-python-base:3.13.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      libmagic1

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

# The dev dependencies, installed before any source so a source edit reuses them.
FROM deps AS deps-dev

RUN --mount=type=cache,target=/opt/uv-cache,uid=1000,gid=1000 \
    uv sync --frozen --no-install-project

# ─── Node / frontend asset build ─────────────────────────────────────────────
FROM node:24-slim AS node_builder
WORKDIR /src
ENV NODE_ENV=production
# The packages, installed before any source so a source edit reuses them.
COPY package.json yarn.lock .yarnrc.yml /src/
COPY .yarn/releases /src/.yarn/releases
RUN yarn install --immutable
COPY . /src
RUN yarn build

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

# ─── Local-dev target (ol-infrastructure local-dev k8s/Tilt stack) ────────────
# FROM deps-dev, not production: production copies the source before the dev
# deps go in, so every source edit would reinstall them. The dev deps include
# granian[reload]. The command and PORT come from the k8s manifest.
FROM deps-dev AS local-dev

COPY --chown=mitodl:mitodl . /src
# The bundles node_builder bakes in. Without them Studio renders an unstyled
# page with no JS.
COPY --from=node_builder --chown=mitodl:mitodl /src/static /src/static
COPY --from=node_builder --chown=mitodl:mitodl /src/webpack-stats.json /src/webpack-stats.json

# As in production. Without it, the app's version check gets a 404 from
# /static/hash.txt on every page change.
ARG GIT_REF
RUN echo "$GIT_REF" >> /src/static/hash.txt

# Reload is switched on here rather than in the k8s manifest because the
# prebuilt production image has no watchfiles, and granian exits if asked to
# reload without it. A short kill timeout stops a worker that won't exit from
# stalling a reload.
ENV GRANIAN_RELOAD=true \
    GRANIAN_WORKERS_KILL_TIMEOUT=1

# ─── Development target ───────────────────────────────────────────────────────
FROM runtime AS development

RUN --mount=type=cache,target=/opt/uv-cache,uid=1000,gid=1000 \
    uv sync --frozen --no-install-project
