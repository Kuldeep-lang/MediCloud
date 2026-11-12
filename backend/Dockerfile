# syntax=docker/dockerfile:1
# MediCloud API - multi-stage build.
#   builder : installs Python dependencies into an isolated virtualenv
#   runtime : slim image with only the venv + application code, running as non-root

ARG PYTHON_VERSION=3.13

# ---------------------------------------------------------------- builder
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Dependencies first: this layer is cached until requirements.txt changes.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    # pip is a build tool, not a runtime dependency (and it vendors its own libraries).
    && python -m pip uninstall -y pip

# ---------------------------------------------------------------- runtime
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG APP_VERSION=1.0.0
ARG GIT_COMMIT=unknown

LABEL org.opencontainers.image.title="medicloud-backend" \
      org.opencontainers.image.description="MediCloud hospital management API (FastAPI)" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_VERSION=${APP_VERSION} \
    GIT_COMMIT=${GIT_COMMIT}

# Apply pending Debian security updates, remove the base image's pip (nothing may be
# installed at runtime; pip also vendors libraries that scanners flag), add a user.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall -y pip \
    && rm -rf /usr/local/bin/pip* \
       "$(python -c 'import ensurepip, os; print(os.path.dirname(ensurepip.__file__))')/_bundled" \
    && groupadd --system --gid 10001 medicloud \
    && useradd --system --uid 10001 --gid medicloud --no-create-home \
       --home-dir /nonexistent --shell /usr/sbin/nologin medicloud

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
# Code stays root-owned and read-only for the app user (it cannot modify itself).
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
# Pre-compile bytecode so a read-only root filesystem needs no __pycache__ writes.
RUN python -m compileall -q /app/app /app/alembic

USER 10001:10001
EXPOSE 8000

# Liveness only (no DB check) - mirrors the Kubernetes liveness probe.
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2).status == 200 else 1)"]

# One process per container: scale with replicas, not workers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
