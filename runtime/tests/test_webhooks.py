from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from runtime.core.dispatch import CanonicalTaskDispatcher
from runtime.core.jobs import JobRuntime
from runtime.webhooks.config import WebhookRuntimeConfig, WebhookSource
from runtime.webhooks.http import WebhookHttpAdapter, create_local_http_server
from runtime.webhooks.models import WebhookEventType
from runtime.webhooks.service import WebhookIngressService
from runtime.webhooks.store import FileWebhookStore, WebhookStoreError


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NOW = "2026-09-23T12:00:00Z"
SIGNED_AT = str(int(datetime.fromisoformat(NOW.replace("Z", "+00:00")).timestamp()))
SIGNING_VALUE = "0123456789abcdef0123456789abcdef"


class Sequence:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"{self.prefix}-{self.value:04d}"


class FaultInjectingWebhookStore(FileWebhookStore):
    def __init__(
        self,
        root: Path,
        *,
        max_records: int = 100,
        fail_reserve_once: bool = False,
        fail_attempt_once: bool = False,
        fail_completed_once: bool = False,
        fail_alias_once: bool = False,
    ) -> None:
        super().__init__(root, max_records=max_records)
        self.fail_reserve_once = fail_reserve_once
        self.fail_attempt_once = fail_attempt_once
        self.fail_completed_once = fail_completed_once
        self.fail_alias_once = fail_alias_once

    def reserve(self, record):
        if self.fail_reserve_once:
            self.fail_reserve_once = False
            raise WebhookStoreError("simulated reservation failure")
        return super().reserve(record)

    def update(self, record) -> None:
        if record.get("audit_state") == "DISPATCH_ATTEMPTED" and self.fail_attempt_once:
            self.fail_attempt_once = False
            raise WebhookStoreError("simulated dispatch-intent failure")
        if record.get("audit_state") == "COMPLETED" and self.fail_completed_once:
            self.fail_completed_once = False
            raise WebhookStoreError("simulated finalization failure")
        super().update(record)

    def bind_aliases(self, record, *, event_id: str, idempotency_key: str):
        if self.fail_alias_once:
            self.fail_alias_once = False
            raise WebhookStoreError("simulated alias persistence failure")
        return super().bind_aliases(
            record,
            event_id=event_id,
            idempotency_key=idempotency_key,
        )


class WebhookIngressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.jobs = JobRuntime(
            self.root / "jobs", clock=lambda: NOW, id_factory=Sequence("job-webhook")
        )
        self.source = WebhookSource(
            source_id="test-source",
            enabled=True,
            allowed_event_types=(WebhookEventType.TASK_SIGNAL,),
            authentication_mode="HMAC_SHA256",
            secret_env="TEST_WEBHOOK_SIGNING_VALUE",
            project_id="project-alpha",
        )
        self.config = WebhookRuntimeConfig(
            sources=(self.source,), max_request_bytes=1024
        )
        self.audit_ids = Sequence("audit")
        self.store = FileWebhookStore(self.root / "webhooks", max_records=100)
        self.service = self._service()
        self.http = WebhookHttpAdapter(self.service)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _service(
        self,
        *,
        config: WebhookRuntimeConfig | None = None,
        repository_root: Path = REPOSITORY_ROOT,
    ) -> WebhookIngressService:
        return WebhookIngressService(
            config or self.config,
            self.store,
            CanonicalTaskDispatcher(self.jobs, repository_root),
            clock=lambda: NOW,
            audit_id_factory=self.audit_ids,
            environment={"TEST_WEBHOOK_SIGNING_VALUE": SIGNING_VALUE},
        )

    @staticmethod
    def event(**overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "event_id": "event-001",
            "event_type": "TASK_SIGNAL",
            "occurred_at": "2026-09-23T11:59:59Z",
            "idempotency_key": "idem-001",
            "project_id": "project-alpha",
            "payload": {
                "task": "Prepare a bounded operations report",
                "task_class": "operations",
            },
            "metadata": {"external_reference": "example-42"},
        }
        value.update(overrides)
        return value

    @staticmethod
    def encode(value: object) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def signature(body: bytes, timestamp: str = SIGNED_AT) -> str:
        digest = hmac.new(
            SIGNING_VALUE.encode("utf-8"),
            timestamp.encode("ascii") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={digest}"

    def ingest(
        self,
        value: object | None = None,
        *,
        source_id: str = "test-source",
        timestamp: str = SIGNED_AT,
        signature: str | None = None,
        service: WebhookIngressService | None = None,
    ):
        body = self.encode(self.event() if value is None else value)
        return (service or self.service).ingest(
            source_id=source_id,
            raw_body=body,
            signature=signature or self.signature(body, timestamp),
            signed_timestamp=timestamp,
        )

    def test_a_valid_signed_event_is_accepted(self) -> None:
        result = self.ingest()
        self.assertEqual(result.status.value, "accepted")
        self.assertIsNotNone(result.job_id)

    def test_b_unknown_source_is_rejected(self) -> None:
        result = self.ingest(source_id="unknown-source")
        self.assertEqual(result.error_code, "unknown_source")
        self.assertEqual(self.jobs.list(), [])

    def test_c_disabled_source_is_rejected(self) -> None:
        disabled = WebhookSource(
            source_id="test-source",
            enabled=False,
            allowed_event_types=(WebhookEventType.TASK_SIGNAL,),
            authentication_mode="HMAC_SHA256",
            secret_env="TEST_WEBHOOK_SIGNING_VALUE",
        )
        service = self._service(config=WebhookRuntimeConfig(sources=(disabled,)))
        result = self.ingest(service=service)
        self.assertEqual(result.error_code, "disabled_source")

    def test_d_invalid_signature_is_rejected(self) -> None:
        result = self.ingest(signature="sha256=" + ("0" * 64))
        self.assertEqual(result.error_code, "invalid_signature")

    def test_e_stale_timestamp_is_rejected(self) -> None:
        stale = "1"
        result = self.ingest(timestamp=stale)
        self.assertEqual(result.error_code, "stale_timestamp")

    def test_f_malformed_json_is_rejected(self) -> None:
        body = b'{"event_id":'
        result = self.service.ingest(
            source_id="test-source",
            raw_body=body,
            signature=self.signature(body),
            signed_timestamp=SIGNED_AT,
        )
        self.assertEqual(result.error_code, "malformed_json")

    def test_g_oversized_body_is_rejected(self) -> None:
        response = self.http.handle(
            method="POST",
            path="/webhooks/test-source",
            headers={"Content-Type": "application/json"},
            body=b"x" * 1025,
        )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.jobs.list(), [])

    def test_h_unsupported_event_type_is_rejected(self) -> None:
        result = self.ingest(self.event(event_type="RUN_COMMAND"))
        self.assertEqual(result.error_code, "unsupported_event_type")

    def test_h2_missing_required_field_is_rejected(self) -> None:
        value = self.event()
        value.pop("idempotency_key")
        result = self.ingest(value)
        self.assertEqual(result.error_code, "invalid_event")

    def test_i_duplicate_event_is_suppressed(self) -> None:
        first = self.ingest()
        second = self.ingest()
        self.assertEqual(first.job_id, second.job_id)
        self.assertEqual(second.status.value, "duplicate")
        self.assertEqual(len(self.jobs.list()), 1)

    def test_j_restart_preserves_dedupe(self) -> None:
        first = self.ingest()
        restarted = self._service()
        second = self.ingest(service=restarted)
        self.assertEqual(second.status.value, "duplicate")
        self.assertEqual(second.job_id, first.job_id)

    def test_j2_duplicate_idempotency_key_is_suppressed(self) -> None:
        first = self.ingest()
        second = self.ingest(
            self.event(event_id="event-002", idempotency_key="idem-001")
        )
        self.assertEqual(second.status.value, "duplicate")
        self.assertEqual(second.job_id, first.job_id)
        record = self.store.list()[0]
        self.assertEqual(record["event_ids"], ["event-001", "event-002"])
        self.assertEqual(record["idempotency_keys"], ["idem-001"])

    def test_j3_changed_content_with_same_identity_is_rejected(self) -> None:
        self.ingest()
        conflict = self.event(
            payload={"task": "Different task", "task_class": "operations"}
        )
        result = self.ingest(conflict)
        self.assertEqual(result.error_code, "idempotency_conflict")
        self.assertEqual(len(self.jobs.list()), 1)

    def test_j31_chained_event_and_idempotency_aliases_cannot_duplicate(self) -> None:
        first = self.ingest()
        event_alias = self.ingest(
            self.event(event_id="event-002", idempotency_key="idem-001")
        )
        key_alias = self.ingest(
            self.event(event_id="event-002", idempotency_key="idem-002")
        )
        chained = self.ingest(
            self.event(event_id="event-003", idempotency_key="idem-002")
        )

        self.assertEqual(event_alias.status.value, "duplicate")
        self.assertEqual(key_alias.status.value, "duplicate")
        self.assertEqual(chained.status.value, "duplicate")
        self.assertEqual(
            {first.job_id, event_alias.job_id, key_alias.job_id, chained.job_id},
            {first.job_id},
        )
        self.assertEqual(len(self.jobs.list()), 1)
        record = self.store.list()[0]
        self.assertEqual(
            record["event_ids"], ["event-001", "event-002", "event-003"]
        )
        self.assertEqual(
            record["idempotency_keys"], ["idem-001", "idem-002"]
        )

    def test_j32_conflicting_alias_is_bound_and_cannot_escape_provenance(self) -> None:
        first = self.ingest()
        self.ingest(self.event(event_id="event-002", idempotency_key="idem-001"))
        conflict = self.ingest(
            self.event(
                event_id="event-002",
                idempotency_key="idem-002",
                payload={"task": "Conflicting task", "task_class": "operations"},
            )
        )
        recovered = self.ingest(
            self.event(event_id="event-003", idempotency_key="idem-002")
        )

        self.assertEqual(conflict.error_code, "idempotency_conflict")
        self.assertEqual(recovered.status.value, "duplicate")
        self.assertEqual(recovered.job_id, first.job_id)
        self.assertEqual(len(self.jobs.list()), 1)

    def test_j33_aliases_survive_restart(self) -> None:
        first = self.ingest()
        self.ingest(self.event(event_id="event-002", idempotency_key="idem-001"))
        restarted = self._service()

        result = self.ingest(
            self.event(event_id="event-002", idempotency_key="idem-002"),
            service=restarted,
        )

        self.assertEqual(result.status.value, "duplicate")
        self.assertEqual(result.job_id, first.job_id)
        self.assertEqual(len(self.jobs.list()), 1)
        self.assertEqual(
            self.store.list()[0]["idempotency_keys"],
            ["idem-001", "idem-002"],
        )

    def test_j34_alias_persistence_failure_fails_closed(self) -> None:
        state_root = self.root / "alias-failure"
        self.store = FaultInjectingWebhookStore(
            state_root,
            fail_alias_once=True,
        )
        service = self._service()
        first = self.ingest(service=service)

        failed = self.ingest(
            self.event(event_id="event-002", idempotency_key="idem-001"),
            service=service,
        )

        self.assertEqual(failed.error_code, "state_unavailable")
        self.assertEqual(len(self.jobs.list()), 1)
        self.assertEqual(self.store.list()[0]["event_ids"], ["event-001"])
        retry = self.ingest(
            self.event(event_id="event-002", idempotency_key="idem-001"),
            service=service,
        )
        self.assertEqual(retry.status.value, "duplicate")
        self.assertEqual(retry.job_id, first.job_id)
        self.assertEqual(
            self.store.list()[0]["event_ids"], ["event-001", "event-002"]
        )

    def test_j35_completed_provenance_survives_rejection_churn_and_restart(self) -> None:
        state_root = self.root / "completed-provenance-retention"
        self.store = FileWebhookStore(state_root, max_records=1)
        service = self._service()
        first = self.ingest(service=service)
        self.ingest(
            self.event(event_id="event-002", idempotency_key="idem-001"),
            service=service,
        )
        bound = self.ingest(
            self.event(event_id="event-002", idempotency_key="idem-002"),
            service=service,
        )
        self.assertEqual(bound.status.value, "duplicate")

        for index in range(4):
            value = self.event(
                event_id=f"rejected-{index}",
                idempotency_key=f"rejected-idem-{index}",
            )
            if index % 2 == 0:
                rejected = self.ingest(
                    value,
                    signature="sha256=" + ("0" * 64),
                    service=service,
                )
            else:
                rejected = self.ingest(
                    value,
                    source_id="unknown-source",
                    service=service,
                )
            self.assertEqual(rejected.status.value, "rejected")

        self.assertEqual(len(self.store.list_audit()), 1)
        self.assertEqual(len(self.store.list_provenance()), 1)
        self.assertEqual(
            len(list(state_root.glob("*.webhook-provenance.json"))), 1
        )

        self.store = FileWebhookStore(state_root, max_records=1)
        restarted = self._service()
        replay = self.ingest(
            self.event(event_id="event-002", idempotency_key="idem-002"),
            service=restarted,
        )

        self.assertEqual(replay.status.value, "duplicate")
        self.assertEqual(replay.job_id, first.job_id)
        self.assertEqual(len(self.jobs.list()), 1)
        provenance = self.store.list_provenance()[0]
        self.assertEqual(provenance["provenance_state"], "COMPLETED")
        self.assertIsNotNone(provenance["finalized_at"])
        self.assertEqual(provenance["event_ids"], ["event-001", "event-002"])
        self.assertEqual(
            provenance["idempotency_keys"], ["idem-001", "idem-002"]
        )

    def test_j36_new_alias_after_audit_churn_uses_retained_provenance(self) -> None:
        state_root = self.root / "post-churn-alias"
        self.store = FileWebhookStore(state_root, max_records=1)
        service = self._service()
        first = self.ingest(service=service)
        self.ingest(
            self.event(event_id="event-002", idempotency_key="idem-001"),
            service=service,
        )
        for index in range(3):
            self.ingest(
                self.event(
                    event_id=f"invalid-{index}",
                    idempotency_key=f"invalid-idem-{index}",
                ),
                signature="sha256=" + ("f" * 64),
                service=service,
            )

        self.store = FileWebhookStore(state_root, max_records=1)
        restarted = self._service()
        chained = self.ingest(
            self.event(event_id="event-002", idempotency_key="idem-002"),
            service=restarted,
        )

        self.assertEqual(chained.status.value, "duplicate")
        self.assertEqual(chained.job_id, first.job_id)
        self.assertEqual(len(self.jobs.list()), 1)
        self.assertEqual(
            self.store.list_provenance()[0]["idempotency_keys"],
            ["idem-001", "idem-002"],
        )

    def test_j37_reverse_alias_chain_survives_audit_churn_and_restart(self) -> None:
        state_root = self.root / "reverse-chain-retention"
        self.store = FileWebhookStore(state_root, max_records=1)
        service = self._service()
        first = self.ingest(
            self.event(event_id="event-A", idempotency_key="idem-X"),
            service=service,
        )
        self.ingest(
            self.event(event_id="event-A", idempotency_key="idem-Y"),
            service=service,
        )
        self.ingest(
            self.event(event_id="event-B", idempotency_key="idem-Y"),
            service=service,
        )
        for index in range(3):
            self.ingest(
                self.event(
                    event_id=f"unknown-{index}",
                    idempotency_key=f"unknown-idem-{index}",
                ),
                source_id="unknown-source",
                service=service,
            )

        self.store = FileWebhookStore(state_root, max_records=1)
        restarted = self._service()
        replay = self.ingest(
            self.event(event_id="event-B", idempotency_key="idem-Y"),
            service=restarted,
        )

        self.assertEqual(replay.status.value, "duplicate")
        self.assertEqual(replay.job_id, first.job_id)
        self.assertEqual(len(self.jobs.list()), 1)
        provenance = self.store.list_provenance()[0]
        self.assertEqual(provenance["event_ids"], ["event-A", "event-B"])
        self.assertEqual(provenance["idempotency_keys"], ["idem-X", "idem-Y"])

    def test_j4_reservation_failure_prevents_dispatch(self) -> None:
        self.store = FaultInjectingWebhookStore(
            self.root / "reservation-failure",
            fail_reserve_once=True,
        )
        service = self._service()

        failed = self.ingest(service=service)

        self.assertEqual(failed.error_code, "state_unavailable")
        self.assertEqual(self.jobs.list(), [])
        retried = self.ingest(service=service)
        self.assertEqual(retried.status.value, "accepted")
        self.assertEqual(len(self.jobs.list()), 1)

    def test_j5_finalization_failure_recovers_by_idempotency_after_restart(self) -> None:
        state_root = self.root / "finalization-failure"
        self.store = FaultInjectingWebhookStore(
            state_root,
            fail_completed_once=True,
        )
        first_service = self._service()

        first = self.ingest(service=first_service)

        self.assertEqual(first.error_code, "state_unavailable")
        self.assertEqual(len(self.jobs.list()), 1)
        self.assertEqual(self.store.list()[0]["audit_state"], "DISPATCH_ATTEMPTED")

        self.store = FileWebhookStore(state_root, max_records=100)
        restarted = self._service()
        retry = self.ingest(
            self.event(event_id="event-002", idempotency_key="idem-001"),
            service=restarted,
        )

        self.assertEqual(retry.status.value, "duplicate")
        self.assertEqual(retry.job_id, first.job_id)
        self.assertEqual(len(self.jobs.list()), 1)
        self.assertEqual(self.store.list()[0]["audit_state"], "COMPLETED")
        chained = self.ingest(
            self.event(event_id="event-002", idempotency_key="idem-002"),
            service=restarted,
        )
        self.assertEqual(chained.status.value, "duplicate")
        self.assertEqual(chained.job_id, first.job_id)
        self.assertEqual(len(self.jobs.list()), 1)

    def test_j51_dispatch_intent_failure_leaves_retryable_reservation(self) -> None:
        self.store = FaultInjectingWebhookStore(
            self.root / "dispatch-intent-failure",
            fail_attempt_once=True,
        )
        service = self._service()

        first = self.ingest(service=service)

        self.assertEqual(first.error_code, "state_unavailable")
        self.assertEqual(self.jobs.list(), [])
        self.assertEqual(self.store.list()[0]["audit_state"], "RESERVED")
        retry = self.ingest(service=service)
        self.assertEqual(retry.status.value, "duplicate")
        self.assertEqual(len(self.jobs.list()), 1)

    def test_j6_incomplete_reservation_is_not_pruned(self) -> None:
        state_root = self.root / "bounded-incomplete"
        self.store = FaultInjectingWebhookStore(
            state_root,
            max_records=1,
            fail_completed_once=True,
        )
        service = self._service()
        first = self.ingest(service=service)
        self.assertEqual(first.error_code, "state_unavailable")

        for index in range(3):
            self.ingest(
                self.event(
                    event_id=f"incomplete-churn-{index}",
                    idempotency_key=f"incomplete-churn-idem-{index}",
                ),
                signature="sha256=" + ("0" * 64),
                service=service,
            )

        self.assertEqual(len(self.jobs.list()), 1)
        self.assertEqual(len(self.store.list_audit()), 1)
        self.assertEqual(
            self.store.list_provenance()[0]["provenance_state"],
            "DISPATCH_ATTEMPTED",
        )

        retry = self.ingest(service=service)
        self.assertEqual(retry.status.value, "duplicate")
        self.assertEqual(len(self.jobs.list()), 1)

    def test_k_event_cannot_create_human_approval(self) -> None:
        result = self.ingest()
        job = self.jobs.show(str(result.job_id))
        self.assertEqual(job["status"], "created")
        self.assertEqual(job["approval_status"], "required")
        self.assertNotIn("approval", job)
        approvals = list((self.root / "approvals").glob("*.approval.json"))
        self.assertEqual(approvals, [])
        with self.assertRaisesRegex(ValueError, "resolved scoped approval"):
            self.jobs.enqueue(str(result.job_id))

    def test_l_approved_text_grants_no_authority(self) -> None:
        payload = {
            "task": "Prepare a report",
            "task_class": "operations",
            "approved": True,
        }
        result = self.ingest(self.event(payload=payload))
        self.assertEqual(result.status.value, "rejected")
        self.assertEqual(self.jobs.list(), [])

    def test_m_event_cannot_invoke_arbitrary_command(self) -> None:
        payload = {
            "task": "Prepare a report",
            "task_class": "operations",
            "command": "whoami",
        }
        result = self.ingest(self.event(payload=payload))
        self.assertEqual(result.status.value, "rejected")

    def test_n_event_cannot_select_provider(self) -> None:
        result = self.ingest(self.event(metadata={"provider": "codex"}))
        self.assertEqual(result.status.value, "rejected")
        self.assertEqual(self.jobs.list(), [])

    def test_o_event_cannot_trigger_git_or_write_authority(self) -> None:
        for field in ("git", "write", "push", "deployment"):
            with self.subTest(field=field):
                value = self.event(
                    event_id=f"event-{field}",
                    idempotency_key=f"idem-{field}",
                    metadata={field: True},
                )
                self.assertEqual(self.ingest(value).status.value, "rejected")
        self.assertEqual(self.jobs.list(), [])

    def test_p_canonical_routing_boundary_is_preserved(self) -> None:
        result = self.ingest()
        job = self.jobs.show(str(result.job_id))
        self.assertEqual(job["agent"], "operations")
        self.assertEqual(job["workflow"], "operations")
        self.assertEqual(job["capability"], "operations_coordination")
        self.assertNotIn("provider", job)

    def test_q_project_binding_is_preserved_and_mismatch_rejected(self) -> None:
        accepted = self.ingest(self.event(project_id=None))
        self.assertEqual(self.jobs.show(str(accepted.job_id))["project_id"], "project-alpha")
        mismatch = self.event(
            event_id="event-mismatch",
            idempotency_key="idem-mismatch",
            project_id="project-beta",
        )
        self.assertEqual(self.ingest(mismatch).error_code, "project_binding_mismatch")

    def test_r_audit_record_is_bounded_and_persisted(self) -> None:
        result = self.ingest()
        record = self.store.list()[0]
        self.assertEqual(record["event_id"], "event-001")
        self.assertEqual(record["verification_result"], "verified")
        self.assertEqual(record["runtime_result_ref"], {"job_id": result.job_id})
        self.assertNotIn("payload", record)
        self.assertNotIn("signature", record)

    def test_s_secrets_are_absent_from_audit_and_job_state(self) -> None:
        self.ingest()
        persisted = "\n".join(
            path.read_text(encoding="utf-8")
            for path in self.root.rglob("*.json")
        )
        self.assertNotIn(SIGNING_VALUE, persisted)
        self.assertNotIn("TEST_WEBHOOK_SIGNING_VALUE", persisted)

    def test_t_generated_webhook_state_is_git_ignored(self) -> None:
        completed = subprocess.run(
            ["git", "check-ignore", "runtime/state/webhooks/probe.json"],
            cwd=REPOSITORY_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_u_http_adapter_rejects_non_post_and_non_json(self) -> None:
        method = self.http.handle(
            method="GET", path="/webhooks/test-source", headers={}, body=b""
        )
        content = self.http.handle(
            method="POST",
            path="/webhooks/test-source",
            headers={"Content-Type": "text/plain"},
            body=b"{}",
        )
        self.assertEqual(method.status_code, 405)
        self.assertEqual(content.status_code, 415)

    def test_u2_non_finite_json_and_extreme_timestamp_fail_closed(self) -> None:
        body = self.encode(self.event()).replace(b'"example-42"', b'NaN')
        malformed = self.service.ingest(
            source_id="test-source",
            raw_body=body,
            signature=self.signature(body),
            signed_timestamp=SIGNED_AT,
        )
        extreme = self.ingest(timestamp="9" * 100)
        self.assertEqual(malformed.error_code, "malformed_json")
        self.assertEqual(extreme.error_code, "invalid_signature")

    def test_v_runtime_routing_failure_is_safe(self) -> None:
        result = self.ingest(
            self.event(
                payload={"task": "Unknown route", "task_class": "not-a-workflow"}
            )
        )
        self.assertEqual(result.error_code, "runtime_routing_failed")
        self.assertEqual(self.jobs.list(), [])

    def test_w_http_server_rejects_public_bind_address(self) -> None:
        with self.assertRaisesRegex(ValueError, "localhost"):
            create_local_http_server(self.service, host="0.0.0.0")

    def test_x_canonical_schema_fields_match_model(self) -> None:
        schema = json.loads(
            (REPOSITORY_ROOT / "schemas" / "webhook-event.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            set(schema["required"]),
            {
                "event_id",
                "source_id",
                "event_type",
                "received_at",
                "idempotency_key",
                "payload",
                "signature_metadata",
                "metadata",
            },
        )

    def test_y_tests_do_not_construct_or_call_external_clients(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (REPOSITORY_ROOT / "runtime" / "webhooks").glob("*.py")
        )
        self.assertNotIn("url" + "open(", source)
        self.assertNotIn("requests" + ".", source)

    def test_z_example_config_loads_without_inline_secret(self) -> None:
        path = REPOSITORY_ROOT / "config" / "webhooks.example.json"
        config = WebhookRuntimeConfig.from_file(path)
        self.assertEqual(config.sources[0].source_id, "example-source")
        tracked = path.read_text(encoding="utf-8").lower()
        self.assertNotIn('"secret":', tracked)


if __name__ == "__main__":
    unittest.main()
