"""Authenticated User Data Stream lifecycle for Testnet reconciliation."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from .binance import BinancePrivateClient


class UserDataStream(Protocol):
    requires_listen_key: bool

    def iter_events(
        self,
        listen_key: str | None,
        on_reconnect: Callable[[], Awaitable[None]] | None = None,
        on_connected: Callable[[], Awaitable[None]] | None = None,
    ) -> AsyncIterator[dict[str, object]]: ...


@dataclass
class UserDataStreamManager:
    client: BinancePrivateClient
    stream: UserDataStream
    keepalive_seconds: int = 30 * 60
    on_account_event: Callable[[dict[str, object]], Awaitable[None]] | None = None
    on_reconnect: Callable[[], Awaitable[None]] | None = None
    on_connected: Callable[[], Awaitable[None]] | None = None

    def __post_init__(self) -> None:
        self.listen_key: str | None = None
        self.last_event_at: datetime | None = None
        self.last_keepalive_at: datetime | None = None
        self.state = "stopped"

    async def run(self) -> None:
        if not self.client.configured:
            self.state = "not_configured"
            return
        self.listen_key = (
            await asyncio.to_thread(self.client.create_user_data_stream)
            if self.stream.requires_listen_key
            else None
        )
        self.state = "running"
        keepalive_task = asyncio.create_task(self._keepalive_loop())
        try:
            async for event in self.stream.iter_events(
                self.listen_key, self._handle_reconnect, self._handle_connected
            ):
                self.last_event_at = datetime.now(timezone.utc)
                if self.on_account_event is not None:
                    await self.on_account_event(event)
        except asyncio.CancelledError:
            raise
        finally:
            keepalive_task.cancel()
            try:
                await keepalive_task
            except asyncio.CancelledError:
                pass
            self.state = "stopped"

    async def _keepalive_loop(self) -> None:
        while True:
            await asyncio.sleep(self.keepalive_seconds)
            if self.listen_key is None or not self.stream.requires_listen_key:
                continue
            await asyncio.to_thread(self.client.keepalive_user_data_stream, self.listen_key)
            self.last_keepalive_at = datetime.now(timezone.utc)

    async def _handle_reconnect(self) -> None:
        if self.on_reconnect is not None:
            await self.on_reconnect()

    async def _handle_connected(self) -> None:
        if self.on_connected is not None:
            await self.on_connected()
