# code/test_stage6_3.py

from data_loader import load_data
from payment_options import build_payment_options
from payment_eligibility import filter_eligible_payment_options
from payment_candidates import generate_payment_candidates


TEST_REQUEST_ID = "request_26"


data = load_data()

request = data["requests"][
    data["requests"]["request_id"] == TEST_REQUEST_ID
].iloc[0]

TEST_USER_ID = request["user_id"]

options = build_payment_options(
    data["payment_options"],
    TEST_REQUEST_ID,
)

profile = data["profiles"][
    data["profiles"]["user_id"] == TEST_USER_ID
].iloc[0]

eligible_options = filter_eligible_payment_options(
    payment_options=options,
    payment_methods_user_will_consider=profile[
        "payment_methods_user_will_consider"
    ],
    max_installment_months=profile[
        "max_installment_months"
    ],
)

candidates = generate_payment_candidates(
    request_date=request["request_date"],
    requested_amount=request["requested_amount"],
    eligible_payment_options=eligible_options,
    payment_methods_user_will_consider=profile["payment_methods_user_will_consider"],
)

print("=" * 60)
print("STAGE 6.3 — PAYMENT CANDIDATE GENERATION")
print("=" * 60)

print(f"Request ID:       {TEST_REQUEST_ID}")
print(f"User ID:          {TEST_USER_ID}")
print(f"Requested amount: {request['requested_amount']}")
print(f"All options:      {len(options)}")
print(f"Eligible options: {len(eligible_options)}")
print(f"Candidates:       {len(candidates)}")
print()

print("ELIGIBLE OPTIONS")
print("-" * 60)

for option in eligible_options:
    print(
        f"{option.payment_option_id} | "
        f"{option.payment_method} | "
        f"{option.number_of_payments} payments | "
        f"{option.total_payable_amount}"
    )

print()

print("GENERATED CANDIDATES")
print("-" * 60)

for candidate in candidates:
    print(f"Candidate: {candidate.candidate_id}")
    print(f"Method:    {candidate.payment_method}")
    print(f"Total:     {candidate.total_amount}")
    print("Payments:")

    for payment_date, amount in candidate.payments:
        print(
            f"  {payment_date.isoformat()} → {amount}"
        )

    print()

print("=" * 60)