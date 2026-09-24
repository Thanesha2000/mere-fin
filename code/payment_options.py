# code/payment_options.py

"""
Stage 6.1 — Payment option loader.

Converts rows from request_payment_options.csv into
clean Python PaymentOption objects.

This stage does NOT:
- decide whether an option is eligible
- simulate payments
- rank payment plans
- choose a recommendation

It only creates a reliable representation of the
payment options supplied by the dataset.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class PaymentOption:
    """
    One seller/provider payment option for a request.
    """

    payment_option_id: str
    request_id: str
    payment_method: str

    payment_amount: Decimal
    number_of_payments: int

    first_payment_date: date
    payment_frequency_days: Optional[int]

    financing_fee: Decimal
    total_payable_amount: Decimal


def _parse_date(value) -> date:
    """
    Convert a date-like value into a Python date.
    """
    if isinstance(value, date):
        return value

    return date.fromisoformat(str(value))


def _parse_optional_int(value) -> Optional[int]:
    """
    Convert a numeric value into int.

    NaN / missing values become None.
    """
    if value is None:
        return None

    try:
        if value != value:  # NaN check
            return None
    except Exception:
        pass

    return int(value)


def build_payment_options(payment_options_df, request_id: str):
    """
    Build PaymentOption objects for one request.

    Parameters
    ----------
    payment_options_df:
        DataFrame containing request_payment_options.csv.

    request_id:
        Request whose payment options should be returned.

    Returns
    -------
    list[PaymentOption]
        Payment options belonging to the requested request.
    """

    request_rows = payment_options_df[
        payment_options_df["request_id"] == request_id
    ]

    options = []

    for _, row in request_rows.iterrows():
        option = PaymentOption(
            payment_option_id=str(row["payment_option_id"]),
            request_id=str(row["request_id"]),
            payment_method=str(row["payment_method"]),
            payment_amount=Decimal(str(row["payment_amount"])),
            number_of_payments=int(row["number_of_payments"]),
            first_payment_date=_parse_date(row["first_payment_date"]),
            payment_frequency_days=_parse_optional_int(
                row["payment_frequency_days"]
            ),
            financing_fee=Decimal(str(row["financing_fee"])),
            total_payable_amount=Decimal(
                str(row["total_payable_amount"])
            ),
        )

        options.append(option)

    return options