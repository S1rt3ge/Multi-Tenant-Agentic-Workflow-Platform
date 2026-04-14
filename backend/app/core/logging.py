import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Emit structured JSON logs for easier ingestion by log platforms."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id
        if hasattr(record, "method"):
            payload["method"] = record.method
        if hasattr(record, "path"):
            payload["path"] = record.path
        if hasattr(record, "status_code"):
            payload["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            payload["duration_ms"] = record.duration_ms
        if hasattr(record, "tenant_id"):
            payload["tenant_id"] = record.tenant_id
        if hasattr(record, "user_id"):
            payload["user_id"] = record.user_id
        if hasattr(record, "client_ip"):
            payload["client_ip"] = record.client_ip
        if hasattr(record, "execution_id"):
            payload["execution_id"] = record.execution_id
        if hasattr(record, "workflow_id"):
            payload["workflow_id"] = record.workflow_id
        if hasattr(record, "agent_name"):
            payload["agent_name"] = record.agent_name
        if hasattr(record, "step_number"):
            payload["step_number"] = record.step_number
        if hasattr(record, "total_tokens"):
            payload["total_tokens"] = record.total_tokens
        if hasattr(record, "total_cost"):
            payload["total_cost"] = record.total_cost
        if hasattr(record, "error"):
            payload["error"] = record.error
        if hasattr(record, "node_id"):
            payload["node_id"] = record.node_id

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def setup_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configure application logging once at startup."""
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )

    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True
