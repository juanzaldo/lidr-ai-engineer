"""Logging de aplicación sin prompts, claves ni cuerpos de excepciones."""

from datetime import datetime, timezone
import json
import logging


class EventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for field in (
            "provider", "model", "input_tokens", "output_tokens",
            "latency_ms", "error_code", "error_type", "environment",
        ):
            if hasattr(record, field):
                data[field] = getattr(record, field)
        return json.dumps(data, ensure_ascii=False)


def configure_logging(level: str) -> None:
    logger = logging.getLogger("estimator")
    logger.setLevel(level.upper())
    logger.propagate = False
    # Reutilizar el handler evita líneas duplicadas al repetir el lifespan.
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(EventFormatter())
        logger.addHandler(handler)
