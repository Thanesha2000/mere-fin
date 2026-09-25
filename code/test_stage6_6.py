from datetime import date
from decimal import Decimal

from payment_candidates import generate_payment_candidates


def main():
    request_date = date(2025, 2, 5)
    requested_amount = Decimal("20000000")

    amount_safe_to_pay = Decimal("12000000")
    earliest_date_for_full_payment = date(2025, 2, 15)
    desired_completion_date = date(2025, 2, 20)

    # IMPORTANT:
    # There is intentionally NO partial_payment PaymentOption.
    #
    # This verifies that partial payment is derived from the
    # user's preference + financial state, not from the
    # request_payment_options.csv file.

    eligible_options = []

    candidates = generate_payment_candidates(
        request_date=request_date,
        requested_amount=requested_amount,
        eligible_payment_options=eligible_options,
        payment_methods_user_will_consider=(
            "partial_payment|full_payment"
        ),
        amount_safe_to_pay=amount_safe_to_pay,
        earliest_date_for_full_payment=(
            earliest_date_for_full_payment
        ),
        desired_completion_date=desired_completion_date,
        allows_partial_payment=True,
    )

    print("=" * 70)
    print("STAGE 6.6 — PAYMENT CANDIDATE GENERATION")
    print("=" * 70)

    print(f"Request date:          {request_date}")
    print(f"Requested amount:      {requested_amount}")
    print(f"Safe amount today:     {amount_safe_to_pay}")
    print(
        "Earliest safe date:    "
        f"{earliest_date_for_full_payment}"
    )
    print(
        "Deadline:              "
        f"{desired_completion_date}"
    )
    print(
        "User methods:          "
        "partial_payment|full_payment"
    )
    print()

    for candidate in candidates:
        print(
            f"Candidate: {candidate.candidate_id}"
        )
        print(
            f"Method:    {candidate.payment_method}"
        )
        print(
            f"Total:     {candidate.total_amount}"
        )
        print(
            f"Payments:  {candidate.payments}"
        )
        print()

    candidate_methods = {
        candidate.payment_method
        for candidate in candidates
    }

    # Partial payment must exist even without a
    # partial_payment PaymentOption.
    assert "partial_payment" in candidate_methods

    # Wait should also exist because the user accepts
    # full_payment and the full amount becomes safe later.
    assert "wait" in candidate_methods

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

    assert (
        partial_candidate.payments[0][1]
        + partial_candidate.payments[1][1]
        == requested_amount
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