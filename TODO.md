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
- [ ] Pass the final independent Phase 7 architecture and security re-review before closure.
