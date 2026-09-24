# code/payment_candidates.py

"""
Stage 6.3 — Payment candidate generation.

This module converts eligible payment options and request
information into concrete payment candidates.

This stage does NOT:
- simulate financial safety
- rank candidates
- choose a recommendation
- modify spending

It only generates the payment plans that later stages
are allowed to evaluate.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from payment_options import PaymentOption


@dataclass(frozen=True)
class PaymentCandidate:
    """
    One concrete payment plan that can be evaluated by the
    financial simulator.
    """

    candidate_id: str
    payment_method: str
    payments: tuple[tuple[date, Decimal], ...]
    total_amount: Decimal
    source_payment_option_id: Optional[str] = None


def _build_installment_payments(
    option: PaymentOption,
) -> tuple[tuple[date, Decimal], ...]:
    """
    Convert an installment payment option into its complete
    chronological payment schedule.
    """

    if option.payment_frequency_days is None:
        raise ValueError(
            "Installment payment option must have "
            "payment_frequency_days."
        )

    payments = []

    for payment_number in range(option.number_of_payments):
        payment_date = (
            option.first_payment_date
            + timedelta(
                days=payment_number * option.payment_frequency_days
            )
        )

        payments.append(
            (
                payment_date,
                option.payment_amount,
            )
        )

    return tuple(payments)


def generate_payment_candidates(
    request_date: date,
    requested_amount: Decimal,
    eligible_payment_options: list[PaymentOption],
):
    """
    Generate concrete payment candidates from eligible
    payment options.

    Supported methods:
    - full_payment
    - installments
    - partial_payment

    Partial payment is generated separately later because
    its second payment depends on the Stage 5b earliest
    safe date.

    Wait is also handled later because its payment date
    depends on Stage 5b.
    """

    request_date = (
        request_date
        if isinstance(request_date, date)
        else date.fromisoformat(str(request_date))
    )

    requested_amount = Decimal(str(requested_amount))

    candidates = []

    for option in eligible_payment_options:

        if option.payment_method == "full_payment":

            payments = (
                (
                    request_date,
                    requested_amount,
                ),
            )

            candidates.append(
                PaymentCandidate(
                    candidate_id=(
                        f"full_payment_{option.payment_option_id}"
                    ),
                    payment_method="full_payment",
                    payments=payments,
                    total_amount=requested_amount,
                    source_payment_option_id=(
                        option.payment_option_id
                    ),
                )
            )

        elif option.payment_method == "installments":

            payments = _build_installment_payments(option)

            candidates.append(
                PaymentCandidate(
                    candidate_id=(
                        f"installments_{option.payment_option_id}"
                    ),
                    payment_method="installments",
                    payments=payments,
                    total_amount=option.total_payable_amount,
                    source_payment_option_id=(
                        option.payment_option_id
                    ),
                )
            )

        elif option.payment_method == "partial_payment":

            # Partial-payment construction requires the
            # Stage 5 maximum safe amount and earliest safe
            # full-payment date.
            #
            # Those values are intentionally NOT calculated
            # in this stage.
            continue

    return candidates