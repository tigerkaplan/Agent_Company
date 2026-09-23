"""Outbound Telegram adapter for canonical operational notifications."""

from __future__ import annotations

from typing import Any, Protocol

from integrations.telegram.client import TelegramApiError
from integrations.telegram.formatter import TelegramNotificationFormatter
from runtime.notifications.models import NotificationEvent
from runtime.notifications.service import NotificationDestination
from runtime.remote.config import RemoteRuntimeConfig


class TelegramNotificationClient(Protocol):
    def send_message(self, *, chat_id: int, text: str) -> dict[str, Any]: ...


class TelegramNotificationTransport:
    channel = "telegram"

    def __init__(
        self,
        *,
        client: TelegramNotificationClient | None,
        config: RemoteRuntimeConfig,
        formatter: TelegramNotificationFormatter | None = None,
    ) -> None:
        self.client = client
        self.config = config
        self.formatter = formatter or TelegramNotificationFormatter()

    def destinations_for(
        self, target_human_identity: str
    ) -> list[NotificationDestination]:
        destinations: list[NotificationDestination] = []
        for user in self.config.users:
            if (
                user.channel != self.channel
                or not user.enabled
                or user.mapped_human_identity != target_human_identity
            ):
                continue
            try:
                platform_user_id = int(user.platform_user_id)
            except ValueError:
                continue
            if platform_user_id <= 0:
                continue
            destination = NotificationDestination(
                channel=self.channel,
                destination_id=str(platform_user_id),
            )
            if destination not in destinations:
                destinations.append(destination)
        return destinations

    def send(
        self, event: NotificationEvent, destination: NotificationDestination
    ) -> dict[str, Any]:
        if self.client is None:
            raise TelegramApiError("Telegram notification transport is unavailable")
        result = self.client.send_message(
            chat_id=int(destination.destination_id),
            text=self.formatter.format(event),
        )
        message_id = result.get("message_id")
        return {
            "message_id": message_id if isinstance(message_id, int) else None,
        }
