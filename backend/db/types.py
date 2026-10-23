"""
Column types and constraint helpers shared by the models.

`UTCDateTime`: every stored point in time is UTC. Python always sees
timezone-aware datetimes (tzinfo=UTC); the column itself stays a plain
`DateTime` (no time zone), which every database stores the same way. Writing a
naive datetime is an error: it would be ambiguous (UTC? Jakarta?), which is
exactly the bug class this type exists to prevent.

`one_of`: a CHECK constraint generated from a `Literal` alias in `schemas.py`,
so the database, the Python types and the generated TypeScript types share one
list of allowed values.
"""

from datetime import UTC, datetime
from typing import Any, get_args

from sqlalchemy import CheckConstraint, DateTime, Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(f"naive datetime {value!r}: use an aware one (clock.utcnow())")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def one_of(column: str, literal: Any) -> CheckConstraint:  # noqa: ANN401 - a typing.Literal
    """CHECK (column IN (...)) from a `Literal[...]` alias; named `<column>_values`."""
    values = get_args(literal)
    if not values or not all(isinstance(v, str) for v in values):
        raise TypeError(f"{literal!r} is not a Literal of strings")
    allowed = ", ".join("'" + v.replace("'", "''") + "'" for v in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=f"{column}_values")
