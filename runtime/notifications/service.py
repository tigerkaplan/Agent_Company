"""Transport-neutral notification delivery and bounded retry service."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Protocol

from runtime.core.jobs import utc_now
from runtime.notifications.models import (
    NotificationError,
    NotificationEvent,
    sanitize_notification_metadata,
)
from runtime.notifications.store import FileNotificationStore


@dataclass(frozen=True)
class NotificationDestination:
    channel: str
    destination_id: str

    @property
    def key(self) -> str:
        return f"{self.channel}:{self.destination_id}"


class NotificationTransport(Protocol):
    channel: str

    def destinations_for(self, target_human_identity: str) -> list[NotificationDestination]: ...

    def send(
        self, event: NotificationEvent, destination: NotificationDestination
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class NotificationResult:
    notification_id: str
    status: str
    attempted: int
    delivered: int
    failed: int
    skipped: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "status": self.status,
            "attempted": self.attempted,
            "delivered": self.delivered,
            "failed": self.failed,
            "skipped": self.skipped,
        }


class NotificationService:
    def __init__(
        self,
        store: FileNotificationStore,
        transports: tuple[NotificationTransport, ...] = (),
        *,
        max_delivery_attempts: int = 3,
        clock=utc_now,
    ) -> None:
        if not 1 <= max_delivery_attempts <= 5:
            raise NotificationError("Notification retry limit is outside the allowed range")
        channels = [transport.channel for transport in transports]
        if len(channels) != len(set(channels)):
            raise NotificationError("Notification transport channels must be unique")
        self.store = store
        self.transports = transports
        self.max_delivery_attempts = max_delivery_attempts
        self.clock = clock

    def emit(self, event: NotificationEvent) -> NotificationResult:
        existing = self.store.load(event.notification_id)
        if existing is not None and existing.get("notification") != event.to_dict():
            raise NotificationError("Notification ID was reused for different content")
        record = existing or {
            "schema_version": 1,
            "notification": event.to_dict(),
            "event_status": "created",
            "deliveries": {},
            "created_at": event.created_at,
            "last_updated_at": event.created_at,
        }
        self.store.save(record)

        destinations: list[tuple[NotificationTransport, NotificationDestination]] = []
        for transport in self.transports:
            for destination in transport.destinations_for(event.target_human_identity):
                if destination.channel != transport.channel:
                    raise NotificationError("Notification destination channel mismatch")
                destinations.append((transport, destination))

        attempted = delivered = failed = skipped = 0
        for transport, destination in destinations:
            delivery = record["deliveries"].setdefault(
                destination.key,
                {
                    "channel": destination.channel,
                    "destination_id": destination.destination_id,
                    "status": "pending",
                    "attempt_count": 0,
                    "first_attempted_at": None,
                    "last_attempted_at": None,
                    "delivered_at": None,
                    "error_code": None,
                    "transport_ref": None,
                },
            )
            if delivery["status"] in {"delivered", "attempted"}:
                skipped += 1
                continue
            if int(delivery["attempt_count"]) >= self.max_delivery_attempts:
                skipped += 1
                continue

            now = self.clock()
            delivery["status"] = "attempted"
            delivery["attempt_count"] = int(delivery["attempt_count"]) + 1
            delivery["first_attempted_at"] = delivery["first_attempted_at"] or now
            delivery["last_attempted_at"] = now
            delivery["error_code"] = None
            record["last_updated_at"] = now
            self.store.save(record)
            attempted += 1
            try:
                raw_evidence = transport.send(event, destination)
                if not isinstance(raw_evidence, dict):
                    raise NotificationError(
                        "Notification transport evidence must be an object"
                    )
                evidence = sanitize_notification_metadata(raw_evidence)
                if len(
                    json.dumps(
                        evidence,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    ).encode("utf-8")
                ) > 2048:
                    raise NotificationError(
                        "Notification transport evidence exceeds the allowed size"
                    )
            except Exception as error:
                delivery["status"] = "failed"
                delivery["error_code"] = type(error).__name__
                failed += 1
            else:
                delivery["status"] = "delivered"
                delivery["delivered_at"] = self.clock()
                delivery["transport_ref"] = deepcopy(evidence)
                delivered += 1
            record["last_updated_at"] = self.clock()
            self.store.save(record)

        if delivered:
            status = "delivered"
        elif failed:
            status = "failed"
        elif destinations:
            status = "duplicate"
        else:
            status = "no_destination"
        return NotificationResult(
            notification_id=event.notification_id,
            status=status,
            attempted=attempted,
            delivered=delivered,
            failed=failed,
            skipped=skipped,
        )
