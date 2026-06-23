from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator, UserDefinedType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class GUID(TypeDecorator[uuid.UUID]):
    """Platform-independent UUID storage for PostgreSQL and SQLite tests."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect: Any) -> str | uuid.UUID | None:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value if isinstance(value, uuid.UUID) else uuid.UUID(str(value)))

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class PGVector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **kw: Any) -> str:
        return f"vector({self.dimensions})"


class VectorType(TypeDecorator[list[float]]):
    """Use pgvector in PostgreSQL and JSON in SQLite tests."""

    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGVector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if dialect.name == "postgresql" and isinstance(value, list):
            return "[" + ",".join(str(float(item)) for item in value) + "]"
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if dialect.name == "postgresql" and isinstance(value, str):
            return [float(item) for item in value.strip("[]").split(",") if item]
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value
