# Build stage
FROM python:3.13.7-slim@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689 as builder
LABEL maintainer="ODL DevOps <mitx-devops@mit.edu>"

# Set environment variables for build
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
WORKDIR /tmp
COPY apt.txt /tmp/apt.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        $(grep -vE "^\s*#" apt.txt | tr "\n" " ") \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /tmp/apt.txt

# Add, and run as, non-root user.
RUN mkdir /src \
    && adduser --disabled-password --gecos "" --uid 1001 mitodl \
    && mkdir /var/media && chown -R mitodl:mitodl /var/media

# Install Python packages
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT="/opt/venv"
ENV PATH="/opt/venv/bin:$PATH"

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:240fb85ab0f263ef12f492d8476aa3a2e4e1e333f7d67fbdd923d00a506a516a /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock /src/
RUN mkdir -p /opt/venv && chown -R mitodl:mitodl /src /opt/venv

USER mitodl
WORKDIR /src
RUN uv sync --frozen --no-install-project

FROM node:24-slim@sha256:879b21aec4a1ad820c27ccd565e7c7ed955f24b92e6694556154f251e4bdb240 AS node_builder
COPY . /src
WORKDIR /src
ENV NODE_ENV=production
RUN yarn install --immutable && yarn build

# Runtime stage
FROM python:3.13.7-slim@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689 as runtime

# Set environment variables for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV="/opt/venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install only runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libxml2 \
        libxslt1.1 \
        libpq5 \
        libxmlsec1 \
        libxmlsec1-openssl \
        libjpeg62-turbo \
        zlib1g \
        libmagic1 \
        net-tools \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary from builder
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /usr/local/bin/uvx /usr/local/bin/uvx

# Add non-root user
RUN adduser --disabled-password --gecos "" --uid 1001 mitodl \
    && mkdir -p /src /var/media \
    && chown -R mitodl:mitodl /src /var/media

# Copy virtual environment from builder
COPY --from=builder --chown=mitodl:mitodl /opt/venv /opt/venv
# Add project
COPY --chown=mitodl:mitodl . /src
WORKDIR /src
RUN find /src -type f -name "*.py" -exec chmod 644 {} \; \
    && find /src -type d -exec chmod 755 {} \;

USER mitodl

EXPOSE 8043
ENV PORT=8043

CMD ["uwsgi", "uwsgi.ini"]

FROM runtime AS production

COPY --from=node_builder --chown=mitodl:mitodl /src/static /src/static
COPY --from=node_builder --chown=mitodl:mitodl /src/webpack-stats.json /src/webpack-stats.json

ARG GIT_REF
RUN echo "$GIT_REF" >> /src/static/hash.txt
