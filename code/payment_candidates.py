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


def _parse_payment_methods(value):
    """
    Convert the user's payment-method preference into a set.

    Example:
        "full_payment|installments"
        ->
        {"full_payment", "installments"}
    """

    if value is None:
        return set()

    text = str(value).strip()

    if not text:
        return set()

    return {
        method.strip()
        for method in text.split("|")
        if method.strip()
    }


def _build_installment_payments(
    option: PaymentOption,
) -> tuple[tuple[date, Decimal], ...]:
    """
    Convert an installment payment option into concrete
    dated payments.
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
                days=payment_number
                * option.payment_frequency_days
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
    """
    Build the two-payment partial-payment plan required by the
    challenge specification.

    Payment 1:
        Safe amount that can be paid today.

    Payment 2:
        Remaining amount on the earliest date when the full
        requested amount becomes safe.
    """

    remaining_amount = (
        requested_amount
        - amount_safe_to_pay
    )

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
    payment_methods_user_will_consider,
    amount_safe_to_pay: Decimal = Decimal("0.00"),
    earliest_date_for_full_payment: Optional[date] = None,
    desired_completion_date: Optional[date] = None,
    allows_partial_payment: bool = False,
):
    """
    Generate structurally valid payment candidates.

    Candidate types:

    1. full_payment
       Pay the complete requested amount immediately.

    2. partial_payment
       Pay the maximum safe amount today and the remainder on
       the earliest date when the complete amount becomes safe.

    3. installments
       Use concrete installment options supplied by the dataset.

    4. wait
       Wait until the requested amount can safely be paid in full.

    Important:
    This function does NOT perform financial simulation.

    Financial safety is checked later by Stage 6.4.

    Also important:
    - User payment preferences determine which methods may be used.
    - Installments require actual eligible payment options.
    - Partial payment does NOT require a partial_payment row in
      request_payment_options.csv.
    """

    request_date = (
        request_date
        if isinstance(request_date, date)
        else date.fromisoformat(str(request_date))
    )

    requested_amount = Decimal(
        str(requested_amount)
    )

    amount_safe_to_pay = Decimal(
        str(amount_safe_to_pay)
    )

    if earliest_date_for_full_payment is not None:
        earliest_date_for_full_payment = (
            earliest_date_for_full_payment
            if isinstance(
                earliest_date_for_full_payment,
                date,
            )
            else date.fromisoformat(
                str(earliest_date_for_full_payment)
            )
        )

    if desired_completion_date is not None:
        desired_completion_date = (
            desired_completion_date
            if isinstance(
                desired_completion_date,
                date,
            )
            else date.fromisoformat(
                str(desired_completion_date)
            )
        )

    allowed_methods = _parse_payment_methods(
        payment_methods_user_will_consider
    )

    candidates = []

    # ===============================================================
    # 1. FULL PAYMENT
    # ===============================================================

    if (
        "full_payment" in allowed_methods
        and amount_safe_to_pay >= requested_amount
    ):
        full_payment_option = next(
            (
                option
                for option in eligible_payment_options
                if option.payment_method
                == "full_payment"
            ),
            None,
        )

        source_payment_option_id = (
            full_payment_option.payment_option_id
            if full_payment_option is not None
            else None
        )

        if source_payment_option_id is not None:
            candidate_id = (
                f"full_payment_"
                f"{source_payment_option_id}"
            )
        else:
            candidate_id = "full_payment_stage5"

        candidates.append(
            PaymentCandidate(
                candidate_id=candidate_id,
                payment_method="full_payment",
                payments=(
                    (
                        request_date,
                        requested_amount,
                    ),
                ),
                total_amount=requested_amount,
                source_payment_option_id=(
                    source_payment_option_id
                ),
            )
        )

    # ===============================================================
    # 2. PARTIAL PAYMENT
    # ===============================================================

    if (
        "partial_payment" in allowed_methods
        and allows_partial_payment
        and Decimal("0")
        < amount_safe_to_pay
        < requested_amount
        and earliest_date_for_full_payment is not None
        and earliest_date_for_full_payment
        > request_date
    ):
        # The complete payment must still happen by the user's
        # requested completion deadline.
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
                    candidate_id=(
                        "partial_payment_stage5"
                    ),
                    payment_method="partial_payment",
                    payments=partial_payments,
                    total_amount=requested_amount,
                    source_payment_option_id=None,
                )
            )

    # ===============================================================
    # 3. INSTALLMENTS
    # ===============================================================

    for option in eligible_payment_options:

        if option.payment_method != "installments":
            continue

        if "installments" not in allowed_methods:
            continue

        payments = _build_installment_payments(
            option
        )

        if not payments:
            continue

        last_payment_date = max(
            payment_date
            for payment_date, _amount in payments
        )

        # Installment plan must finish by the requested deadline.
        if (
            desired_completion_date is not None
            and last_payment_date
            > desired_completion_date
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
                total_amount=(
                    option.total_payable_amount
                ),
                source_payment_option_id=(
                    option.payment_option_id
                ),
            )
        )

    # ===============================================================
    # 4. WAIT FOR FULL PAYMENT
    # ===============================================================

    if (
        "full_payment" in allowed_methods
        and amount_safe_to_pay < requested_amount
        and earliest_date_for_full_payment is not None
        and earliest_date_for_full_payment
        > request_date
    ):
        # Waiting is useful only if the requested amount becomes
        # safe before the user's completion deadline.
        if (
            desired_completion_date is None
            or earliest_date_for_full_payment
            <= desired_completion_date
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