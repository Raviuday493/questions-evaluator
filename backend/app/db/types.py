from typing import Any, List, Optional

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator

# JSONB on PostgreSQL, plain JSON elsewhere (SQLite for tests).
PortableJSON = JSON().with_variant(JSONB(), "postgresql")


class EmbeddingVector(TypeDecorator):
    """pgvector `vector(dim)` column on PostgreSQL, JSON array on other dialects."""

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Optional[List[float]], dialect):
        if value is None:
            return None
        values = [float(v) for v in value]
        if len(values) != self.dim:
            raise ValueError(f"Embedding has {len(values)} dimensions, expected {self.dim}")
        # On PostgreSQL pgvector's own bind processor serialises the list.
        return values

    def process_result_value(self, value: Any, dialect) -> Optional[List[float]]:
        if value is None:
            return None
        return [float(v) for v in value]
