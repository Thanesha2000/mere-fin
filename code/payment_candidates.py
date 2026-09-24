from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from payment_options import PaymentOption


@dataclass(frozen=True)
class PaymentCandidate:
    candidate_id: str
    payment_method: str
    payments: tuple[tuple[date, Decimal], ...]
    total_amount: Decimal
    source_payment_option_id: Optional[str] = None


def _build_installment_payments(
    option: PaymentOption,
) -> tuple[tuple[date, Decimal], ...]:
    if option.payment_frequency_days is None:
        raise ValueError(
            "Installment payment option must have payment_frequency_days."
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


def _build_partial_payment(
    request_date: date,
    requested_amount: Decimal,
    amount_safe_to_pay: Decimal,
    earliest_date_for_full_payment: date,
) -> tuple[tuple[date, Decimal], ...]:
    remaining_amount = requested_amount - amount_safe_to_pay

    return (
        (
            request_date,
            amount_safe_to_pay,
        ),
        (
            earliest_date_for_full_payment,
            remaining_amount,
        ),
    )


def generate_payment_candidates(
    request_date: date,
    requested_amount: Decimal,
    eligible_payment_options: list[PaymentOption],
    amount_safe_to_pay: Decimal = Decimal("0.00"),
    earliest_date_for_full_payment: Optional[date] = None,
    desired_completion_date: Optional[date] = None,
    allows_partial_payment: bool = False,
):
    """
    Generate all payment candidates that are structurally permitted
    by the request and payment preferences.

    Candidate types:
    - full_payment
    - partial_payment
    - installments
    - wait

    Safety is determined using Stage 5 / Stage 5b outputs:
    - amount_safe_to_pay
    - earliest_date_for_full_payment

    This function does not perform financial simulation.
    """

    request_date = (
        request_date
        if isinstance(request_date, date)
        else date.fromisoformat(str(request_date))
    )

    requested_amount = Decimal(str(requested_amount))
    amount_safe_to_pay = Decimal(str(amount_safe_to_pay))

    if earliest_date_for_full_payment is not None:
        earliest_date_for_full_payment = (
            earliest_date_for_full_payment
            if isinstance(earliest_date_for_full_payment, date)
            else date.fromisoformat(
                str(earliest_date_for_full_payment)
            )
        )

    if desired_completion_date is not None:
        desired_completion_date = (
            desired_completion_date
            if isinstance(desired_completion_date, date)
            else date.fromisoformat(
                str(desired_completion_date)
            )
        )

    candidates = []

    allowed_methods = {
        option.payment_method
        for option in eligible_payment_options
    }

    # ---------------------------------------------------------------
    # 1. FULL PAYMENT
    # ---------------------------------------------------------------
    #
    # Full payment is possible immediately only when:
    #
    # amount_safe_to_pay >= requested_amount
    #
    # and the user accepts full_payment.
    #
    if (
        "full_payment" in allowed_methods
        and amount_safe_to_pay >= requested_amount
    ):
        full_payment_option = next(
            option
            for option in eligible_payment_options
            if option.payment_method == "full_payment"
        )

        candidates.append(
            PaymentCandidate(
                candidate_id=(
                    f"full_payment_"
                    f"{full_payment_option.payment_option_id}"
                ),
                payment_method="full_payment",
                payments=(
                    (
                        request_date,
                        requested_amount,
                    ),
                ),
                total_amount=requested_amount,
                source_payment_option_id=(
                    full_payment_option.payment_option_id
                ),
            )
        )

    # ---------------------------------------------------------------
    # 2. PARTIAL PAYMENT
    # ---------------------------------------------------------------
    #
    # Exactly two payments:
    #
    # payment 1 = amount_safe_to_pay today
    # payment 2 = remaining amount on earliest safe date
    #
    if (
        "partial_payment" in allowed_methods
        and allows_partial_payment
        and Decimal("0") < amount_safe_to_pay < requested_amount
        and earliest_date_for_full_payment is not None
        and earliest_date_for_full_payment > request_date
    ):
        second_payment_amount = (
            requested_amount - amount_safe_to_pay
        )

        if (
            desired_completion_date is None
            or earliest_date_for_full_payment
            <= desired_completion_date
        ):
            partial_payments = _build_partial_payment(
                request_date=request_date,
                requested_amount=requested_amount,
                amount_safe_to_pay=amount_safe_to_pay,
                earliest_date_for_full_payment=(
                    earliest_date_for_full_payment
                ),
            )

            candidates.append(
                PaymentCandidate(
                    candidate_id="partial_payment_stage5",
                    payment_method="partial_payment",
                    payments=partial_payments,
                    total_amount=requested_amount,
                    source_payment_option_id=None,
                )
            )

    # ---------------------------------------------------------------
    # 3. INSTALLMENTS
    # ---------------------------------------------------------------
    #
    # Installments must exactly follow a supplied payment option.
    # We only reject an option here if its final payment misses
    # the desired completion date.
    #
    for option in eligible_payment_options:
        if option.payment_method != "installments":
            continue

        payments = _build_installment_payments(option)

        if not payments:
            continue

        last_payment_date = max(
            payment_date
            for payment_date, _amount in payments
        )

        if (
            desired_completion_date is not None
            and last_payment_date > desired_completion_date
        ):
            continue

        candidates.append(
            PaymentCandidate(
                candidate_id=(
                    f"installments_"
                    f"{option.payment_option_id}"
                ),
                payment_method="installments",
                payments=payments,
                total_amount=option.total_payable_amount,
                source_payment_option_id=(
                    option.payment_option_id
                ),
            )
        )

    # ---------------------------------------------------------------
    # 4. WAIT
    # ---------------------------------------------------------------
    #
    # Wait means:
    #
    # - full_payment is accepted
    # - full payment is NOT safe today
    # - a future safe date exists
    # - that date is within the desired completion deadline
    #
    if (
        "full_payment" in allowed_methods
        and amount_safe_to_pay < requested_amount
        and earliest_date_for_full_payment is not None
        and earliest_date_for_full_payment > request_date
        and (
            desired_completion_date is None
            or earliest_date_for_full_payment
            <= desired_completion_date
        )
    ):
        candidates.append(
            PaymentCandidate(
                candidate_id="wait_full_payment",
                payment_method="wait",
                payments=(
                    (
                        earliest_date_for_full_payment,
                        requested_amount,
                    ),
                ),
                total_amount=requested_amount,
                source_payment_option_id=None,
            )
        )

    return candidates