"""
schemas.py
----------
Shared base of the API models (Pydantic): `Schema`, the stock-code type and
the investing style. Each feature keeps its own models in `<feature>/schemas.py`.
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict


class Schema(BaseModel):
    """Base of every API model. In the OpenAPI document, fields with a default are
    still *required* in responses (the server always sends them), so the
    generated frontend types don't mark them optional."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


def stock_code(value: str) -> str:
    """An IDX stock code as stored: upper case, without Yahoo's ".JK" suffix, so
    "bbca", "BBCA" and old links with "BBCA.JK" all mean the same stock."""
    return value.strip().upper().removesuffix(".JK")


# A stock code from a client (request body field or path parameter).
StockCode = Annotated[str, AfterValidator(stock_code)]


# How the user invests: long-term fundamentals vs short-term (swing) price action.
InvestingStyle = Literal["investor", "trader"]
