"""
Webhook Server for Enterprise Events
Enterprise-grade webhook server for event-driven architecture and real-time integrations
Implements webhook management, event processing, and HTTP/HTTPS endpoints
"""

from typing import *
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from typing_extensions import TypedDict
import asyncio
import json
import logging
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing_extensions import Literal

logger = logging.getLogger(__name__)

class WebhookEvent(BaseModel):
    """"Webhook event model"""
    event_id: str
    event_type: str
    source: str
    timestamp: datetime
    data: Dict[str, Any]
    headers: Dict[str, str] = {}
    signature: Optional[str] = None
    retry_count: int = 0
    status: Literal["pending", "processing", "sent", "failed", "retry"] = "pending"
    metadata: Dict[str, Any] = {}

class WebhookConfig(BaseModel):
    """Webhook configuration"""
    webhook_id: str
    url: str
    events: List[str]
    secret: Optional[str] = None
    retry_policy: Dict[str, Any] = {}
    headers: Dict[str, str] = {}
    active: bool = True
    format: str = "json"
    content_type: str = "application/json"
    timeout: int = 30
    max_retries: int = 3
    backoff_multiplier: float = 2.0
    metadata: Dict[str, Any] = {}
class WebhookServer:
    """Webhook Server Implementation"""

    def __init__(self, config: WebhookConfig):
        self.config = config
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.processed_events: List[WebhookEvent] = []
        self.is_running = False
        self.server = None
        self.processor = None

    async def start(self) -> None:
        """Start webhook server"""
        logger.info(f"Starting webhook server at {self.config.url}")

        try:
            # Register webhook
            self.webhooks[self.config.webhook_id] = self.config

            # Create FastAPI application
            self.app = FastAPI(
                title="Webhook Server",
                description="Enterprise webhook server for event-driven architecture",
                version="1.0.0"
            )

            # Setup routes
            self._setup_routes()

            # Setup event processor
            self.processor = asyncio.create_task(self._event_processor_loop())

            # Start server
            import uvicorn

            config = uvicorn.Config(
                app=self.app,
                host="0.0.0.0",
                port=8000,
                log_level="info"
            )

            self.server = uvicorn.Server(config)
            self.is_running = True

            logger.info("Webhook server started successfully")
            await self.server.serve()

        except Exception as e:
            logger.error(f"Failed to start webhook server: {e}")
            self.is_running = False
            raise

    async def stop(self) -> None:
        """Stop webhook server"""
        if self.server:
            self.server.shutdown()
            self.is_running = False

        if self.processor:
            self.processor.cancel()

        logger.info("Webhook server stopped")

    def _setup_routes(self) -> None:
        """Setup API routes"""

        @self.app.get("/health")
        async def health_check(request: Request) -> Dict[str, str]:
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
                "registered_webhooks": len(self.webhooks)
            }

        @self.app.get("/webhooks")
        async def list_webhooks(request: Request) -> Dict[str, Any]:
            return {
                "webhooks": list(self.webhooks.values()),
                "count": len(self.webhooks)
            }

        @self.app.post("/webhooks")
        async def register_webhook(request: Request, webhook_data: WebhookConfig) -> Dict[str, str]:
            webhook_id = f"webhook_{datetime.now().timestamp()}"
            webhook_data.webhook_id = webhook_id
            webhook_data.active = True

            self.webhooks[webhook_id] = webhook_data

            logger.info(f"Registered webhook {webhook_id} at {webhook_data.url} for events: {webhook_data.events}")

            return {
                "webhook_id": webhook_id,
                "status": "registered",
                "message": f"Webhook registered at {webhook_data.url}"
            }

        @self.app.get("/webhooks/{webhook_id}")
        async def get_webhook(self, request: Request, webhook_id: str) -> Dict[str, Any]:
            if webhook_id not in self.webhooks:
                return {"error": "Webhook not found"}, 404

            webhook = self.webhooks[webhook_id]
            return {
                "webhook_id": webhook.webhook_id,
                "url": webhook.url,
                "events": webhook.events,
                "active": webhook.active,
                "format": webhook.format,
                "content_type": webhook.content_type,
                "timeout": webhook.timeout,
                "max_retries": webhook.max_retries,
                "metadata": webhook.metadata
            }

        @self.app.put("/webhooks/{webhook_id}")
        async def update_webhook(self, request: Request, webhook_id: str, webhook_data: Dict[str, Any]) -> Dict[str, str]:
            if webhook_id not in self.webhooks:
                return {"error": "Webhook not found"}, 404

            # Update webhook configuration
            webhook = self.webhooks[webhook_id]
            for key, value in webhook_data.items():
                if hasattr(webhook, key):
                    setattr(webhook, key, value)

            logger.info(f"Updated webhook {webhook_id}")
            return {
                "message": f"Webhook {webhook_id} updated",
                "status": "updated"
            }

        @self.app.delete("/webhooks/{webhook_id}")
        async def delete_webhook(self, request: Request, webhook_id: str) -> Dict[str, str]:
            if webhook_id not in self.webhooks:
                return {"error": "Webhook not found"}, 404

            del self.webhooks[webhook_id]
            logger.info(f"Deleted webhook {webhook_id}")
            return {
                "message": f"Webhook {webhook_id} deleted",
                "status": "deleted"
            }

        @self.app.post("/webhook")
        async def receive_webhook(self, request: Request, webhook_data: Dict[str, Any]) -> Dict[str, str]:
            # Create webhook event
            event = WebhookEvent(
                event_id=f"event_{datetime.now().timestamp()}",
                event_type=webhook_data.get("event_type", "generic"),
                source=webhook_data.get("source", "webhook"),
                timestamp=datetime.now(),
                data=webhook_data.get("data", {}),
                headers=dict(request.headers),
                metadata=webhook_data.get("metadata", {})
            )

            # Add to event queue for processing
            asyncio.create_task(self._queue_event_for_processing(event))

            logger.info(f"Received webhook event {event.event_id} of type {event.event_type}")

            return {
                "event_id": event.event_id,
                "status": "received",
                "message": "Webhook event received and queued for processing"
            }

        @self.app.get("/events")
        async def list_events(request: Request) -> Dict[str, Any]:
            return {
                "events": [event.dict() for event in self.processed_events],
                "count": len(self.processed_events)
            }

    async def _event_processor_loop(self) -> None:
        """Event processor loop"""
        while self.is_running:
            try:
                # Wait for event from queue
                event = await self.event_queue.get()

                # Process event
                await self._process_event(event)

            except Exception as e:
                logger.error(f"Error in event processor loop: {e}")
                await asyncio.sleep(60)  # Wait before retry

    async def _process_event(self, event: WebhookEvent) -> None:
        """Process webhook event"""
        try:
            # Determine which webhooks should receive this event
            relevant_webhooks = [
                webhook for webhook in self.webhooks.values()
                if webhook.active and event.event_type in webhook.events
            ]

            if not relevant_webhooks:
                logger.debug(f"No webhooks configured for event type: {event.event_type}")
                return

            # Send event to relevant webhooks
            for webhook in relevant_webhooks:
                await self._send_to_webhook(webhook, event)

            # Store processed event
            self.processed_events.append(event)

            # Keep only recent events (last 1000)
            if len(self.processed_events) > 1000:
                self.processed_events = self.processed_events[-1000:]

        except Exception as e:
            logger.error(f"Failed to process event {event.event_id}: {e}")
            event.status = "failed"
            # TODO: Implement retry logic

    async def _send_to_webhook(self, webhook: WebhookConfig, event: WebhookEvent) -> None:
        """Send event to webhook"""
        try:
            import httpx

            # Prepare webhook payload
            payload = event.data
            if webhook.format == "json":
                headers = {
                    "Content-Type": webhook.content_type,
                    "User-Agent": "Webhook-Server/1.0"
                }
                headers.update(webhook.headers)

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        webhook.url,
                        json=payload,
                        headers=headers,
                        timeout=webhook.timeout
                    )

                    if response.status_code >= 200 and response.status_code < 300:
                        event.status = "sent"
                        logger.info(f"Sent event {event.event_id} to webhook {webhook.webhook_id}")
                    else:
                        raise Exception(f"Webhook responded with status {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to send event {event.event_id} to webhook {webhook.webhook_id}: {e}")
            event.status = "failed"
            # TODO: Implement retry logic

    async def _queue_event_for_processing(self, event: WebhookEvent) -> None:
        """Queue event for processing"""
        await self.event_queue.put(event)

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        return {
            "status": "healthy" if self.is_running else "stopped",
            "registered_webhooks": len(self.webhooks),
            "queued_events": self.event_queue.qsize(),
            "processed_events": len(self.processed_events),
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }

    def get_webhook_stats(self) -> Dict[str, Any]:
        """Get webhook statistics"""
        events_by_type = {}
        for event in self.processed_events:
            events_by_type[event.event_type] = events_by_type.get(event.event_type, 0) + 1

        return {
            "webhooks": {
                "total": len(self.webhooks),
                "active": len([w for w in self.webhooks.values() if w.active]),
                "inactive": len([w for w in self.webhooks.values() if not w.active])
            },
            "events": {
                "total": len(self.processed_events),
                "status_breakdown": {
                    "pending": len([e for e in self.processed_events if e.status == "pending"]),
                    "processing": len([e for e in self.processed_events if e.status == "processing"]),
                    "sent": len([e for e in self.processed_events if e.status == "sent"]),
                    "failed": len([e for e in self.processed_events if e.status == "failed"]),
                    "retry": len([e for e in self.processed_events if e.status == "retry"])
                },
                "by_type": events_by_type
            },
            "queue": {
                "size": self.event_queue.qsize(),
                "max_size": 10000  # TODO: Make configurable
            }
        }