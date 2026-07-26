"""
Event Bus — Central orchestration for publish-subscribe messaging.

Design Decision:
    The EventBus composes the Registry, Dispatcher, and Middleware chain.
    It implements the Publisher protocol.
    It uses an `asyncio.Queue` for sync-to-async boundary crossing
    (``publish_sync`` fires and forgets into the queue).
"""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional

from loguru import logger

from .dispatcher import Dispatcher
from .event_types import Event
from .exceptions import MiddlewareError
from .handlers import EventHandler
from .middleware import Middleware
from .publisher import Publisher
from .registry import Registry


class EventBus(Publisher):
    """Central event hub connecting publishers and subscribers.

    Responsibilities:
        - Manage the middleware chain.
        - Handle incoming events (sync and async).
        - Delegate routing to the Registry.
        - Delegate execution to the Dispatcher.
        - Manage the background task for sync events.
    """

    def __init__(self) -> None:
        self.registry = Registry()
        self.dispatcher = Dispatcher()
        self._middlewares: List[Middleware] = []

        # Background queue for sync publishing
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task[None]] = None

    # ==================================================================
    #  Lifecycle
    # ==================================================================

    async def start(self) -> None:
        """Start the background worker for sync publishing."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._queue_worker())
            logger.debug("EventBus background worker started")

    async def stop(self) -> None:
        """Stop the background worker."""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            logger.debug("EventBus background worker stopped")

    async def _queue_worker(self) -> None:
        """Consume events from the sync queue and publish them."""
        while True:
            try:
                event = await self._queue.get()
                try:
                    await self.publish(event)
                except Exception as e:
                    logger.exception("EventBus worker error: {err}", err=str(e))
                finally:
                    self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("EventBus worker unexpected error: {err}", err=str(e))

    # ==================================================================
    #  Middleware
    # ==================================================================

    def add_middleware(self, middleware: Middleware) -> None:
        """Add a middleware to the execution chain.

        Middlewares are executed in the order they are added.
        """
        self._middlewares.append(middleware)

    # ==================================================================
    #  Subscription API
    # ==================================================================

    async def subscribe(
        self,
        event_pattern: str,
        handler: EventHandler,
        priority: int = 100,
        once: bool = False,
        subscriber_id: str = "",
    ) -> str:
        """Register a handler for an event pattern.

        Returns:
            The ``subscriber_id``.
        """
        sub = await self.registry.register(
            event_pattern=event_pattern,
            handler=handler,
            priority=priority,
            once=once,
            subscriber_id=subscriber_id,
        )
        return sub.subscriber_id

    async def unsubscribe(self, subscriber_id: str) -> bool:
        """Remove a subscriber by ID."""
        return await self.registry.unregister(subscriber_id)

    # ==================================================================
    #  Publishing API (Publisher Protocol)
    # ==================================================================

    async def publish(self, event: Event) -> None:
        """Publish an event and wait for all handlers to complete."""
        # Step 1: Lookup subscribers
        subscribers = await self.registry.get_matching(event.event_name)

        if not subscribers:
            # We don't raise here by default because in a highly decoupled
            # system, emitting an event nobody listens to is normal.
            # But we log it at trace level.
            logger.trace("No subscribers for event: {name}", name=event.event_name)
            return

        # Step 2: Build the middleware continuation chain
        async def execute_dispatch(evt: Event) -> None:
            once_ids = await self.dispatcher.dispatch(evt, subscribers)
            await self.registry.remove_once_subscribers(once_ids)

        # Build the chain from the inside out (backwards)
        chain_head = execute_dispatch
        for mw in reversed(self._middlewares):
            def make_link(m: Middleware, next_fn: Any) -> Any:
                async def link(evt: Event) -> None:
                    try:
                        await m(evt, next_fn)
                    except Exception as e:
                        # Wrap middleware errors
                        name = m.__class__.__name__
                        raise MiddlewareError(name, e) from e
                return link
            chain_head = make_link(mw, chain_head)

        # Step 3: Execute the chain
        await chain_head(event)

    async def publish_batch(self, events: List[Event]) -> None:
        """Publish multiple events sequentially."""
        for event in events:
            await self.publish(event)

    def publish_sync(self, event: Event) -> None:
        """Fire-and-forget publish from synchronous code."""
        try:
            self._queue.put_nowait(event)
        except Exception as e:
            logger.error("Failed to enqueue sync event: {err}", err=str(e))
