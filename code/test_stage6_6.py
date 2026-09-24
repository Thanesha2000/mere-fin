from datetime import date
from decimal import Decimal

from payment_candidates import generate_payment_candidates
from payment_options import PaymentOption


def main():
    request_date = date(2025, 2, 5)
    requested_amount = Decimal("20000000")

    amount_safe_to_pay = Decimal("12000000")
    earliest_date_for_full_payment = date(2025, 2, 15)
    desired_completion_date = date(2025, 2, 20)

    eligible_options = [
        PaymentOption(
            payment_option_id="payment_option_full",
            request_id="request_212",
            payment_method="full_payment",
            payment_amount=requested_amount,
            number_of_payments=1,
            first_payment_date=request_date,
            payment_frequency_days=None,
            financing_fee=Decimal("0"),
            total_payable_amount=requested_amount,
        ),
        PaymentOption(
            payment_option_id="payment_option_partial",
            request_id="request_212",
            payment_method="partial_payment",
            payment_amount=Decimal("0"),
            number_of_payments=2,
            first_payment_date=request_date,
            payment_frequency_days=None,
            financing_fee=Decimal("0"),
            total_payable_amount=requested_amount,
        ),
    ]

    candidates = generate_payment_candidates(
        request_date=request_date,
        requested_amount=requested_amount,
        eligible_payment_options=eligible_options,
        amount_safe_to_pay=amount_safe_to_pay,
        earliest_date_for_full_payment=(
            earliest_date_for_full_payment
        ),
        desired_completion_date=desired_completion_date,
        allows_partial_payment=True,
    )

    print("=" * 70)
    print("STAGE 6.6 — PARTIAL + WAIT CANDIDATE GENERATION")
    print("=" * 70)

    print(f"Request date:          {request_date}")
    print(f"Requested amount:      {requested_amount}")
    print(f"Safe amount today:     {amount_safe_to_pay}")
    print(f"Earliest safe date:    {earliest_date_for_full_payment}")
    print(f"Deadline:              {desired_completion_date}")
    print()

    for candidate in candidates:
        print(f"Candidate: {candidate.candidate_id}")
        print(f"Method:    {candidate.payment_method}")
        print(f"Total:     {candidate.total_amount}")
        print(f"Payments:  {candidate.payments}")
        print()

    candidate_methods = {
        candidate.payment_method
        for candidate in candidates
    }

    assert "partial_payment" in candidate_methods
    assert "wait" in candidate_methods
    assert "full_payment" not in candidate_methods

    partial_candidate = next(
        candidate
        for candidate in candidates
        if candidate.payment_method == "partial_payment"
    )

    assert partial_candidate.payments == (
        (
            date(2025, 2, 5),
            Decimal("12000000"),
        ),
        (
            date(2025, 2, 15),
            Decimal("8000000"),
        ),
    )

    wait_candidate = next(
        candidate
        for candidate in candidates
        if candidate.payment_method == "wait"
    )

    assert wait_candidate.payments == (
        (
            date(2025, 2, 15),
            Decimal("20000000"),
        ),
    )

    print("=" * 70)
    print("STAGE 6.6 TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()