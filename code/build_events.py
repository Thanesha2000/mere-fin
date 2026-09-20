# code/build_events.py
"""
Bridges Stage 1 raw DataFrame -> Stage 2's typed RawEvent objects.

Why this file exists: data_loader.py returns plain pandas DataFrames
with no dtype guarantees — a blank amount could come through as NaN
(float) or empty string depending on pandas' mood, dates come through
as strings, and nothing stops a stray 0.0 from meaning "blank" instead
of "actually zero". Stage 2 (reconcile.py) expects typed RawEvent
objects with real Decimal/date/None values. This file is the one place
that conversion happens, so every downstream stage trusts the types
without re-checking.
"""
from decimal import Decimal
from datetime import date
import pandas as pd

from reconcile import RawEvent


def _to_decimal_or_none(v) -> Decimal | None:
    """Blank/NaN/empty -> None, never 0. Real value -> Decimal, never float."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
        return None
    return Decimal(str(v))


def _to_date_or_none(v) -> date | None:
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
        return None
    return pd.to_datetime(v).date()


def _clean_optional_str(v) -> str | None:
    """For linked_event_id / flexibility — pandas gives NaN for empty cells, not None."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    v = str(v).strip()
    return v if v else None


def events_df_to_raw_events(events_df: pd.DataFrame) -> list[RawEvent]:
    """
    Converts the raw financial_events.csv DataFrame into a list of
    RawEvent dataclasses, one per row, with correct types throughout.
    Missing/optional columns are handled via .get() so this doesn't
    crash if a column is absent in some dataset variant.
    """
    out: list[RawEvent] = []
    for _, row in events_df.iterrows():
        out.append(RawEvent(
            event_id=row["event_id"],
            user_id=row["user_id"],
            event_type=row.get("event_type", ""),
            description=row.get("description", ""),
            category=row.get("category", ""),
            direction=row["direction"],
            amount=_to_decimal_or_none(row.get("amount")),
            currency=row["currency"],
            event_date=_to_date_or_none(row["event_date"]),
            settlement_date=_to_date_or_none(row.get("settlement_date")),
            status=row["status"],
            linked_event_id=_clean_optional_str(row.get("linked_event_id")),
            flexibility=_clean_optional_str(row.get("flexibility")),
            minimum_allowed_amount=_to_decimal_or_none(row.get("minimum_allowed_amount")),
        ))
    return out