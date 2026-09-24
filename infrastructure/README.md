# Infrastructure

This directory contains the canonical Phase 8 hosting and deployment design.
It does not contain a deployment, service definition, container image, public
endpoint, credential, or infrastructure automation.

## Status

- Phase 8A: PASS / COMPLETED on 2026-09-24; design and discovery only.
- Phase 8B: NEXT / NOT STARTED.
- Current runtime: local-first, file-backed, and single-worker.
- Deployment: not performed.
- Docker, VPS, operating-system service, Hermes, and public webhook exposure:
  not installed or enabled.
- Merge and deployment authority: absent.

## Documents

- `HOST_ARCHITECTURE.md` defines the host boundary, process and persistence
  models, startup and recovery behavior, Docker and VPS assessments, acceptance
  criteria, and proposed implementation stages.
- `SECURITY_MODEL.md` defines production secret handling, ingress and authority
  boundaries, backup safety, and the Phase 8 threat model.

## Authority Boundary

The host is an availability mechanism only. It may keep the existing runtime
processes alive and provide durable local storage. It must not classify work,
select business routing or providers, decide approvals or reviews, grant Git,
merge, release, or deployment authority, or reinterpret canonical runtime
state.

Any future implementation remains subordinate to `../CONSTITUTION.md`,
`../AGENTS.md`, the existing runtime authority surfaces, and exact human
approval for production deployment.
