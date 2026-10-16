"""Helpers shared by the admin API routers: pagination, filters, CSV export."""
import csv
import io
import math
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from fastapi import HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

EXPORT_ROW_LIMIT = 10_000


class Page:
    """Validated `page` / `limit` query parameters."""

    def __init__(self, page: int = Query(1, ge=1, le=100_000), limit: int = Query(20, ge=1, le=100)):
        self.page = page
        self.limit = limit

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def paginate(db: Session, query, page: Page, order_by: Sequence, transform: Callable[[Any], Any], unique: bool = False) -> Dict:
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    result = db.scalars(query.order_by(*order_by).offset(page.offset).limit(page.limit))
    rows = result.unique().all() if unique else result.all()
    return {
        "items": [transform(r) for r in rows],
        "page": page.page,
        "limit": page.limit,
        "total": total,
        "total_pages": max(1, math.ceil(total / page.limit)),
    }


def not_found(label: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")


def conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def invalid(message: str) -> HTTPException:
    return HTTPException(status_code=422, detail=message)


def parse_id(value: Any, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        raise not_found(label)


def parse_optional_uuid(value: Optional[str], field: str) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        raise invalid(f"{field} must be a valid id")


def like_pattern(search: str) -> str:
    """Case-insensitive LIKE pattern with the user's wildcards escaped (use with escape='\\')."""
    cleaned = search.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{cleaned}%"


def parse_date_range(date_from: Optional[date], date_to: Optional[date]) -> tuple:
    """Inclusive calendar-day range (UTC) -> (start datetime, exclusive end datetime)."""
    if date_from and date_to and date_from > date_to:
        raise invalid("'from' must be on or before 'to'")
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc) if date_from else None
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc) if date_to else None
    return start, end


def parse_bool_filter(value: Optional[str], field: str) -> Optional[bool]:
    if value is None or value == "":
        return None
    lowered = value.lower()
    if lowered in ("true", "1", "yes"):
        return True
    if lowered in ("false", "0", "no"):
        return False
    raise invalid(f"{field} must be true or false")


def parse_enum_list(value: Optional[str], enum_cls, field: str) -> List:
    if not value:
        return []
    try:
        return [enum_cls(v.strip().upper()) for v in value.split(",") if v.strip()]
    except ValueError:
        raise invalid(f"{field} must be one of: {', '.join(e.value for e in enum_cls)}")


def _csv_safe(value: Any) -> Any:
    """Neutralise spreadsheet formula injection in exported cells."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


def csv_response(filename: str, headers: List[str], rows: Iterable[Iterable[Any]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_csv_safe(v) for v in row])
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


def iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
