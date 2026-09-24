# Notification Runtime

The Phase 7 notification runtime converts bounded canonical runtime events into
informational delivery attempts. It is provider-neutral and does not approve,
execute, classify, mutate jobs, invoke Git, or grant authority.

Implemented event types are `APPROVAL_REQUESTED`, `APPROVAL_APPROVED`,
`APPROVAL_REJECTED`, `JOB_COMPLETED`, `JOB_FAILED`, and `RUNTIME_ERROR`. Events
use deterministic IDs and delivery evidence is
stored atomically below ignored `runtime/state/notifications/`. A delivered or
in-flight event is not resent after restart. Failed delivery may be retried by
re-emitting the same event, with a maximum of three attempts.

Runtime hooks are optional. Notification failures are isolated after canonical
job, approval, or scheduler state is persisted. Configured notification targets
are mapped to enabled remote identities; a missing or disabled destination
causes no outbound send.

Automatic CLI wiring requires both a local `notification_targets` list and the
global `--enable-notifications` flag. The notification test command is preview
only unless its explicit `--send` option is supplied.

Each state record separates the canonical event (`event_status: created`) from
per-destination `attempted`, `delivered`, and `failed` evidence. The state write
is atomic. Delivered and in-flight attempts are not repeated after restart;
failed attempts may be retried by re-emitting the identical event, up to the
configured bound of three attempts.

Notifications disclose IDs and compact status only. They do not contain raw
provider output, project files, full task payloads, credentials, environment
values, or bot tokens.

Approval notifications include the exact approval ID and authorization
fingerprint only while a decision is pending for the existing `/approve` or
`/reject` command. Resolution notifications omit the fingerprint and contain
only bounded action, status, actor, timestamp, and job references. Delivery is
informational and never resolves or rolls back the approval itself.
