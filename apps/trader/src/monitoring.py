"""Structured logs and optional webhook alerts for operational failures."""

import json
import logging
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from .settings import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("strategy_id", "symbol", "event", "order_id", "client_order_id"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def configure_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(handler.formatter, JsonFormatter) for handler in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def emit_alert(message: str, **context: object) -> None:
    logger = logging.getLogger("algodesk.alert")
    logger.warning(message, extra={"event": "alert", **context})
    if not settings.alert_webhook_url:
        return
    payload = json.dumps({"text": message, **context}).encode("utf-8")
    request = Request(
        settings.alert_webhook_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "AlgoDesk/0.1"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5):  # noqa: S310 - URL is explicit operator configuration
            pass
    except Exception as exc:  # noqa: BLE001 - alert delivery must not stop trading state handling
        logger.error(
            "alert webhook delivery failed",
            extra={"event": "alert_webhook_error", "error": str(exc)},
        )
