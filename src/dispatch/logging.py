"""Configuração de logging estruturado (JSON) via ``structlog``.

Logs em JSON com contexto por contato (ex.: ``contact_id``, ``telefone``)
tornam o disparo rastreável e adequado a ingestão por ferramentas de
observabilidade — bem mais útil que ``print()``.
"""

from __future__ import annotations

import logging
import sys

import structlog
from structlog.typing import FilteringBoundLogger


def configure_logging(level: str = "INFO") -> None:
    """Configura o structlog para emitir JSON no nível informado."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(**context: object) -> FilteringBoundLogger:
    """Retorna um logger com contexto vinculado (ex.: ``contact_id``, ``telefone``)."""
    return structlog.get_logger().bind(**context)
