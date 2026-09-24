"""Verified webhook ingress mapped only to the canonical task dispatcher."""

from __future__ import annotations

import hashlib
import hmac
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from uuid import uuid4

from runtime.core.dispatch import CanonicalDispatchError, CanonicalTaskDispatcher
from runtime.core.jobs import utc_now
from runtime.webhooks.config import WebhookRuntimeConfig
from runtime.webhooks.models import (
    WebhookContractError,
    WebhookEvent,
    WebhookIngressResult,
    WebhookResultStatus,
)
from runtime.webhooks.store import FileWebhookStore, WebhookStoreError


class WebhookIngressService:
    """Authenticate raw bytes before producing and routing a canonical event."""

    def __init__(
        self,
        config: WebhookRuntimeConfig,
        store: FileWebhookStore,
        dispatcher: CanonicalTaskDispatcher,
        *,
        clock: Callable[[], str] = utc_now,
        audit_id_factory: Callable[[], str] | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.config = config
        self.store = store
        self.dispatcher = dispatcher
        self.clock = clock
        self.audit_id_factory = audit_id_factory or (
            lambda: f"webhook-audit-{uuid4().hex}"
        )
        self.environment = environment

    def ingest(
        self,
        *,
        source_id: str,
        raw_body: bytes,
        signature: str | None,
        signed_timestamp: str | None,
    ) -> WebhookIngressResult:
        received_at = self.clock()
        event_fields: dict[str, str | None] = {
            "event_id": None,
            "event_type": None,
            "idempotency_key": None,
        }
        if len(raw_body) > self.config.max_request_bytes:
            return self._reject(
                received_at,
                source_id,
                event_fields,
                "request_too_large",
                "Webhook request exceeds the configured size bound",
                verification="not_verified",
            )
        source = self.config.source(source_id)
        if source is None:
            return self._reject(
                received_at,
                source_id,
                event_fields,
                "unknown_source",
                "Webhook source is not trusted",
                verification="failed",
            )
        if not source.enabled:
            return self._reject(
                received_at,
                source_id,
                event_fields,
                "disabled_source",
                "Webhook source is disabled",
                verification="failed",
            )
        try:
            self._verify(
                source.resolve_secret(self.environment),
                raw_body=raw_body,
                signature=signature,
                signed_timestamp=signed_timestamp,
                received_at=received_at,
            )
        except WebhookContractError as error:
            code = "stale_timestamp" if "replay window" in str(error) else "invalid_signature"
            return self._reject(
                received_at,
                source_id,
                event_fields,
                code,
                str(error),
                verification="failed",
            )
        try:
            body = self._parse_json(raw_body)
            for key in event_fields:
                value = body.get(key)
                if isinstance(value, str):
                    event_fields[key] = value[:256]
            event = WebhookEvent.from_body(
                body,
                source_id=source_id,
                received_at=received_at,
                signature_metadata={
                    "mode": "HMAC_SHA256",
                    "signed_timestamp": signed_timestamp,
                    "verified": True,
                },
                configured_project_id=source.project_id,
            )
            if event.event_type not in source.allowed_event_types:
                raise WebhookContractError(
                    "Webhook event_type is not allowed for this source"
                )
        except WebhookContractError as error:
            message = str(error)
            if "JSON" in message:
                code = "malformed_json"
            elif "event_type" in message:
                code = "unsupported_event_type"
            elif "project_id" in message:
                code = "project_binding_mismatch"
            else:
                code = "invalid_event"
            return self._reject(
                received_at,
                source_id,
                event_fields,
                code,
                message,
                verification="verified",
            )
        event_fingerprint = self._event_fingerprint(event)
        reservation = self._reservation_record(event, event_fingerprint)
        try:
            existing = self.store.reserve(reservation)
        except WebhookStoreError:
            return self._result(
                WebhookResultStatus.FAILED,
                received_at,
                source_id,
                event_fields,
                "Webhook replay reservation is unavailable",
                "state_unavailable",
            )
        if existing is not None:
            try:
                existing = self.store.bind_aliases(
                    existing,
                    event_id=event.event_id,
                    idempotency_key=event.idempotency_key,
                )
            except WebhookStoreError:
                return self._result(
                    WebhookResultStatus.FAILED,
                    received_at,
                    source_id,
                    event_fields,
                    "Webhook provenance aliases could not be persisted",
                    "state_unavailable",
                )
            expected_fingerprint = (
                event_fingerprint
                if existing.get("fingerprint_version") == 2
                else self._legacy_event_fingerprint(event)
            )
            if existing.get("event_fingerprint") != expected_fingerprint:
                return self._result(
                    WebhookResultStatus.REJECTED,
                    received_at,
                    source_id,
                    event_fields,
                    "Webhook event identity conflicts with reserved content",
                    "idempotency_conflict",
                )
            reservation = existing
        return self._resume_reservation(
            event,
            reservation,
            event_fields,
            duplicate=existing is not None,
        )

    def _resume_reservation(
        self,
        event: WebhookEvent,
        reservation: dict[str, Any],
        event_fields: dict[str, str | None],
        *,
        duplicate: bool,
    ) -> WebhookIngressResult:
        state = reservation.get("provenance_state", reservation.get("audit_state"))
        job_id = reservation.get("runtime_result_ref", {}).get("job_id")
        if state == "COMPLETED":
            return self._result(
                WebhookResultStatus.DUPLICATE,
                event.received_at,
                event.source_id,
                event_fields,
                "Webhook event was already processed",
                None,
                job_id=job_id,
            )
        if state == "FAILED":
            return self._result(
                WebhookResultStatus.FAILED,
                event.received_at,
                event.source_id,
                event_fields,
                "Webhook event previously failed canonical routing",
                str(reservation.get("error_code") or "runtime_routing_failed"),
            )
        if state not in {"RESERVED", "DISPATCH_ATTEMPTED"}:
            return self._result(
                WebhookResultStatus.FAILED,
                event.received_at,
                event.source_id,
                event_fields,
                "Webhook reservation state is invalid",
                "state_unavailable",
            )

        provenance = str(reservation["canonical_provenance"])
        if state == "RESERVED":
            attempting = deepcopy(reservation)
            attempting["audit_state"] = "DISPATCH_ATTEMPTED"
            attempting["provenance_state"] = "DISPATCH_ATTEMPTED"
            attempting["dedupe_result"] = "duplicate" if duplicate else "new"
            try:
                self.store.update(attempting)
            except WebhookStoreError:
                return self._result(
                    WebhookResultStatus.FAILED,
                    event.received_at,
                    event.source_id,
                    event_fields,
                    "Webhook dispatch intent could not be persisted",
                    "state_unavailable",
                )
            reservation = attempting

        try:
            job = self.dispatcher.find_existing(provenance)
            if job is None:
                job = self.dispatcher.dispatch(
                    task=event.payload["task"],
                    task_class=event.payload["task_class"],
                    created_by=provenance,
                    input_refs=[
                        {
                            "ref_type": "other",
                            "ref": (
                                "webhook-event:"
                                f"{event.source_id}:{reservation['event_id']}"
                            ),
                            "description": "Authenticated canonical webhook event",
                        }
                    ],
                    project_id=event.project_id,
                    approval_reason=(
                        "Webhook-originated work requires explicit human approval before execution"
                    ),
                    request_approval=False,
                )
        except CanonicalDispatchError:
            failed = deepcopy(reservation)
            failed["audit_state"] = "FAILED"
            failed["provenance_state"] = "FAILED"
            failed["finalized_at"] = event.received_at
            failed["runtime_status"] = WebhookResultStatus.FAILED.value
            failed["error_code"] = "runtime_routing_failed"
            try:
                self.store.update(failed)
            except WebhookStoreError:
                pass
            return self._result(
                WebhookResultStatus.FAILED,
                event.received_at,
                event.source_id,
                event_fields,
                "Webhook event could not be routed through the canonical dispatcher",
                "runtime_routing_failed",
            )

        accepted = self._result(
            WebhookResultStatus.ACCEPTED,
            event.received_at,
            event.source_id,
            event_fields,
            "Webhook event accepted into the canonical approval lifecycle",
            None,
            job_id=str(job["job_id"]),
        )
        completed = deepcopy(reservation)
        completed["audit_state"] = "COMPLETED"
        completed["provenance_state"] = "COMPLETED"
        completed["finalized_at"] = accepted.processed_at
        completed["processed"] = True
        completed["runtime_status"] = WebhookResultStatus.ACCEPTED.value
        completed["runtime_result_ref"] = {"job_id": accepted.job_id}
        completed["error_code"] = None
        try:
            self.store.update(completed)
        except WebhookStoreError:
            return self._result(
                WebhookResultStatus.FAILED,
                event.received_at,
                event.source_id,
                event_fields,
                "Webhook work exists but reservation finalization is incomplete",
                "state_unavailable",
                job_id=accepted.job_id,
            )
        if duplicate:
            return self._result(
                WebhookResultStatus.DUPLICATE,
                event.received_at,
                event.source_id,
                event_fields,
                "Webhook event was recovered without duplicate work",
                None,
                job_id=accepted.job_id,
            )
        return accepted

    def _reservation_record(
        self, event: WebhookEvent, event_fingerprint: str
    ) -> dict[str, Any]:
        identity = json.dumps(
            [event.source_id, event.idempotency_key],
            separators=(",", ":"),
            ensure_ascii=True,
        )
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        provenance_id = f"webhook:{event.source_id}:idempotency:{digest}"
        return {
            "audit_id": f"webhook-reservation-{digest}",
            "reservation": True,
            "audit_state": "RESERVED",
            "provenance_id": provenance_id,
            "provenance_state": "RESERVED",
            "event_id": event.event_id,
            "source_id": event.source_id,
            "event_type": event.event_type.value,
            "received_at": event.received_at,
            "created_at": event.received_at,
            "finalized_at": None,
            "verification_result": "verified",
            "dedupe_result": "new",
            "runtime_status": None,
            "runtime_result_ref": {},
            "error_code": None,
            "idempotency_key": event.idempotency_key,
            "event_ids": [event.event_id],
            "idempotency_keys": [event.idempotency_key],
            "processed": False,
            "event_fingerprint": event_fingerprint,
            "fingerprint_version": 2,
            "canonical_provenance": provenance_id,
        }

    def _verify(
        self,
        secret: bytes,
        *,
        raw_body: bytes,
        signature: str | None,
        signed_timestamp: str | None,
        received_at: str,
    ) -> None:
        if signature is None or signed_timestamp is None:
            raise WebhookContractError("Webhook signature headers are required")
        if not signed_timestamp.isascii() or not signed_timestamp.isdigit():
            raise WebhookContractError("Webhook signed timestamp is invalid")
        try:
            received = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise WebhookContractError("Webhook runtime clock is invalid") from error
        try:
            signed = datetime.fromtimestamp(int(signed_timestamp), timezone.utc)
        except (OSError, OverflowError, ValueError) as error:
            raise WebhookContractError("Webhook signed timestamp is invalid") from error
        if received.tzinfo is None:
            raise WebhookContractError("Webhook runtime clock must include a timezone")
        if abs((received.astimezone(timezone.utc) - signed).total_seconds()) > (
            self.config.replay_window_seconds
        ):
            raise WebhookContractError("Webhook signed timestamp is outside the replay window")
        if not signature.startswith("sha256=") or len(signature) != 71:
            raise WebhookContractError("Webhook signature is invalid")
        supplied = signature[7:]
        if any(character not in "0123456789abcdef" for character in supplied):
            raise WebhookContractError("Webhook signature is invalid")
        signed_bytes = signed_timestamp.encode("ascii") + b"." + raw_body
        expected = hmac.new(secret, signed_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied):
            raise WebhookContractError("Webhook signature is invalid")

    @staticmethod
    def _parse_json(raw_body: bytes) -> dict[str, Any]:
        try:
            text = raw_body.decode("utf-8")
        except UnicodeDecodeError as error:
            raise WebhookContractError("Webhook body is not valid UTF-8 JSON") from error

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise WebhookContractError("Webhook JSON contains duplicate keys")
                value[key] = item
            return value

        try:
            value = json.loads(
                text,
                object_pairs_hook=unique_object,
                parse_constant=lambda _: (_ for _ in ()).throw(
                    WebhookContractError("Webhook body contains non-finite JSON")
                ),
            )
        except json.JSONDecodeError as error:
            raise WebhookContractError("Webhook body is malformed JSON") from error
        if not isinstance(value, dict):
            raise WebhookContractError("Webhook body must be a JSON object")
        return value

    def _reject(
        self,
        received_at: str,
        source_id: str,
        event_fields: dict[str, str | None],
        code: str,
        message: str,
        *,
        verification: str,
    ) -> WebhookIngressResult:
        result = self._result(
            WebhookResultStatus.REJECTED,
            received_at,
            source_id,
            event_fields,
            message,
            code,
        )
        self._audit(
            result,
            idempotency_key=event_fields.get("idempotency_key"),
            verification=verification,
            dedupe="not_checked",
            processed=False,
        )
        return result

    def _result(
        self,
        status: WebhookResultStatus,
        received_at: str,
        source_id: str,
        event_fields: dict[str, str | None],
        message: str,
        error_code: str | None,
        *,
        job_id: str | None = None,
    ) -> WebhookIngressResult:
        return WebhookIngressResult(
            status=status,
            message=message,
            processed_at=received_at,
            event_id=event_fields.get("event_id"),
            source_id=source_id,
            event_type=event_fields.get("event_type"),
            job_id=job_id,
            error_code=error_code,
        )

    def _audit(
        self,
        result: WebhookIngressResult,
        *,
        idempotency_key: str | None,
        verification: str,
        dedupe: str,
        processed: bool,
        event_fingerprint: str | None = None,
    ) -> bool:
        record = {
            "audit_id": self.audit_id_factory(),
            "reservation": False,
            "audit_state": (
                "REJECTED"
                if result.status is WebhookResultStatus.REJECTED
                else "FAILED"
            ),
            "event_id": result.event_id,
            "source_id": result.source_id,
            "event_type": result.event_type,
            "received_at": result.processed_at,
            "verification_result": verification,
            "dedupe_result": dedupe,
            "runtime_status": result.status.value,
            "runtime_result_ref": (
                {"job_id": result.job_id} if result.job_id is not None else {}
            ),
            "error_code": result.error_code,
            "idempotency_key": idempotency_key,
            "processed": processed,
            "event_fingerprint": event_fingerprint,
        }
        try:
            self.store.save(record)
        except WebhookStoreError:
            # Accepted dispatch remains idempotent through its deterministic created_by
            # key; the caller is told persistence failed and may safely retry.
            return False
        return True

    @staticmethod
    def _event_fingerprint(event: WebhookEvent) -> str:
        value = {
            "source_id": event.source_id,
            "event_type": event.event_type.value,
            "occurred_at": event.occurred_at,
            "payload": event.payload,
            "project_id": event.project_id,
            "metadata": event.metadata or {},
        }
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _legacy_event_fingerprint(event: WebhookEvent) -> str:
        value = {
            "source_id": event.source_id,
            "event_type": event.event_type.value,
            "occurred_at": event.occurred_at,
            "idempotency_key": event.idempotency_key,
            "payload": event.payload,
            "project_id": event.project_id,
            "metadata": event.metadata or {},
        }
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
