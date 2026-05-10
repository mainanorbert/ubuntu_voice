"""Portable embedding column: pgvector on PostgreSQL, JSON text on SQLite (tests)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Text, TypeDecorator


class EmbeddingVector(TypeDecorator):
    """Store a dense float vector as ``VECTOR(n)`` on Postgres or JSON text on SQLite."""

    impl = Text
    cache_ok = True

    def __init__(self, dimension: int) -> None:
        """Attach the fixed embedding width expected by the database column."""
        super().__init__()
        self.dimension = dimension

    def load_dialect_impl(self, dialect: Any) -> Any:
        """Use pgvector on PostgreSQL and plain text JSON elsewhere."""
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(self.dimension))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: list[float] | None, dialect: Any) -> Any:
        """Serialize a Python list of floats for the active dialect."""
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(self, value: Any, dialect: Any) -> list[float] | None:
        """Deserialize database values back into a list of floats."""
        if value is None:
            return None
        if dialect.name == "postgresql":
            if isinstance(value, list):
                return [float(x) for x in value]
            return [float(x) for x in list(value)]
        if isinstance(value, (bytes, bytearray)):
            return [float(x) for x in json.loads(value.decode("utf-8"))]
        return [float(x) for x in json.loads(str(value))]
