"""DuckDB adapter – infrastructure layer database connection.

All SQL lives here. Domain layer remains pure Python.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

import duckdb
import structlog

logger = structlog.get_logger(__name__)

_DB_PATH = os.getenv("DUCKDB_PATH", "data/saasguard.duckdb")


@contextmanager
def get_connection(read_only: bool = True) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Context manager for a DuckDB connection.

    Args:
        read_only: If True (default), opens a read-only connection safe for
                   concurrent API workers. Set False for write operations.

    Yields:
        An active DuckDB connection that is closed on exit.
    """
    conn = duckdb.connect(database=_DB_PATH, read_only=read_only)
    logger.debug("duckdb.connection.opened", path=_DB_PATH, read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()
        logger.debug("duckdb.connection.closed")
