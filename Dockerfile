# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.14.3-slim-bookworm@sha256:f21c0d5a44c56805654c15abccc1b2fd576c8d93aca0a3f74b4aba2dc92510e2
FROM ${PYTHON_IMAGE}

ARG AGENT_COMPANY_REVISION=unknown
ARG AGENT_COMPANY_VERSION=phase8d

LABEL org.opencontainers.image.title="Agent Company" \
      org.opencontainers.image.description="Provider-neutral Agent Company runtime" \
      org.opencontainers.image.revision="${AGENT_COMPANY_REVISION}" \
      org.opencontainers.image.version="${AGENT_COMPANY_VERSION}"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0

RUN groupadd --gid 10001 agentcompany \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin agentcompany \
    && install -d -o 10001 -g 10001 -m 0700 /var/lib/agent-company \
    && install -d -o 10001 -g 10001 -m 0700 /tmp/agent-company

WORKDIR /opt/agent-company
COPY --chown=10001:10001 CONSTITUTION.md AGENTS.md INTENT.md PROJECT_STATE.md ROADMAP.md TODO.md README.md ./
COPY --chown=10001:10001 agents ./agents
COPY --chown=10001:10001 config ./config
COPY --chown=10001:10001 infrastructure/docker ./infrastructure/docker
COPY --chown=10001:10001 integrations ./integrations
COPY --chown=10001:10001 orchestrator ./orchestrator
COPY --chown=10001:10001 providers ./providers
COPY --chown=10001:10001 runtime ./runtime
COPY --chown=10001:10001 schemas ./schemas
COPY --chown=10001:10001 shared ./shared
COPY --chown=10001:10001 skills ./skills

USER 10001:10001

ENTRYPOINT ["python", "-m", "runtime.cli"]
CMD ["--help"]
