# Agent Company TODO

## Phase 7 Planning

- [x] Define the Phase 7 threat and authority model in `runtime/remote/AUTHORITY_MODEL.md`.
- [x] Define the remote-command contract in `runtime/remote/COMMAND_CONTRACT.md`.
- [x] Define the Telegram connector/runtime boundary in `integrations/telegram/CONTRACT.md`.
- [x] Define remote approval and rejection interaction in `runtime/remote/AUTHORITY_MODEL.md`.
- [x] Determine the webhook runtime ingestion boundary in `integrations/webhooks/CONTRACT.md`.
- [x] Define Phase 7 acceptance criteria in `runtime/remote/README.md`.

## Phase 7 Implementation Tasks

- [x] Add a canonical RemoteCommand model and deterministic command ID/idempotency validation.
- [x] Add explicit remote identity mapping from stable platform IDs to trusted human or machine identities without tracked secrets.
- [x] Add a RemoteCommandService that calls only existing runtime/orchestrator authority surfaces.
- [x] Persist remote approval audit evidence for authenticated remote actor, source channel, platform identity, command ID, and approval binding.
- [x] Add duplicate update/callback replay protection with persisted command audit records.
- [x] Add Telegram transport adapter tests without calling Telegram APIs.
- [x] Add authenticated local-first webhook ingress with signed trusted machine events, durable replay/idempotency state, canonical routing, bounded audit evidence, and rejected human-approval attempts.
- [x] Add remote notification formatting for approval requested/resolved, job completed/failed, and scheduler/runtime errors.
- [x] Add deny-by-default command permissions and action/project-scoped remote approval policy.
- [x] Restrict Telegram command handling to authenticated private chats.
- [x] Persist remote approval intent before mutation and expose incomplete mutation audit state.
- [x] Reject excessive future command timestamps with bounded clock skew.
- [x] Run the full Phase 6/7 regression suite after security remediation (424/424 PASS on 2026-09-24).
- [x] Pass the final repository-backed Phase 7 architecture and security review
  (142/142 targeted and 430/430 full runtime tests PASS on 2026-09-24).
- [x] Record Phase 7 as COMPLETED / CLOSED; retain a different-provider
  full-repository audit as recommended future validation rather than a gate.

## Phase 8A Design — PASS / COMPLETED

- [x] Inventory current always-on-safe runtime assumptions without claiming distributed guarantees.
- [x] Define the canonical host, process, persistent-state, secret, ingress, backup, and authority boundaries.
- [x] Assess Docker, a vendor-neutral VPS target, Telegram long polling, public webhook prerequisites, and optional Hermes use.
- [x] Define the Phase 8 threat model, acceptance criteria, and implementation stages in `infrastructure/`.
- [x] Close the recorded Phase 7 independent review gate before Phase 8 implementation.
- [x] Record Phase 8A as PASS / COMPLETED with no deployment and no Phase 8B implementation.
- [x] Implement Phase 8B host configuration, canonical persistence paths,
  initialization, and readiness checks without deploying.
- [x] Repair the Phase 8B independent-review security and correctness findings.
- [x] Pass the Phase 8B independent implementation/security re-review and
  record Phase 8B as COMPLETED / CLOSED.
- [x] Implement Phase 8C background process lifecycle and deterministic recovery
  validation without public exposure.
- [x] Repair the three Phase 8C review blockers: provider-enable bypass,
  signal-callback reentrancy, and startup/stop-request overwrite.
- [x] Complete the successful Phase 8C independent implementation/security
  re-review and record Phase 8C as COMPLETED / CLOSED.
- [ ] Phase 8D is NEXT / NOT STARTED; perform any Docker adaptation only after
  Linux controlled-write behavior is independently reviewed.
- [ ] Require exact human approval before Phase 8E VPS deployment or any later public exposure.
- [ ] Complete Phase 8F backup/recovery, Phase 8G smoke testing, and Phase 8H final independent security review.

Non-blocking Phase 8C future hardening: different-provider full-repository
audit, real subprocess singleton-race validation, native Windows signal/ACL
validation, and more race-resistant status-lock probing. Race-resistant
directory-handle containment remains a separate non-blocking Phase 8B item.
