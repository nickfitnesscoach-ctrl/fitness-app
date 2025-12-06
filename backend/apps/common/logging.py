"""
Custom logging formatters for structured logging.

Provides JSON formatter for production environments,
enabling easier log aggregation and analysis.
"""

import json
import logging
import traceback
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.
    
    Output format:
    {
        "timestamp": "2025-01-15T12:34:56.789Z",
        "level": "INFO",
        "logger": "apps.billing.services",
        "message": "Payment created",
        "module": "services",
        "function": "create_payment",
        "line": 123,
        "process": 1234,
        "thread": 5678,
        "extra": {...}  // any extra fields
    }
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.thread,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info) if record.exc_info[0] else None,
            }
        
        # Add extra fields (user_id, payment_id, etc.)
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'pathname', 'process', 'processName', 'relativeCreated',
            'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
            'taskName', 'message'
        }
        
        extra = {}
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                try:
                    json.dumps(value)  # Check if serializable
                    extra[key] = value
                except (TypeError, ValueError):
                    extra[key] = str(value)
        
        if extra:
            log_data["extra"] = extra
        
        return json.dumps(log_data, ensure_ascii=False)


class StructuredLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds structured context to log messages.
    
    Usage:
        logger = StructuredLoggerAdapter(logging.getLogger(__name__), {})
        logger.info("Payment created", extra={"user_id": 123, "amount": 299})
    """
    
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra or {})
    
    def process(self, msg, kwargs):
        # Merge adapter's extra with call-time extra
        extra = {**self.extra, **kwargs.get('extra', {})}
        kwargs['extra'] = extra
        return msg, kwargs
    
    def with_context(self, **context):
        """
        Create a new adapter with additional context.
        
        Usage:
            request_logger = logger.with_context(request_id="abc123")
            request_logger.info("Processing request")
        """
        new_extra = {**self.extra, **context}
        return StructuredLoggerAdapter(self.logger, new_extra)


def get_logger(name: str) -> StructuredLoggerAdapter:
    """
    Get a structured logger by name.
    
    Usage:
        from apps.common.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened", extra={"user_id": 123})
    """
    return StructuredLoggerAdapter(logging.getLogger(name), {})
