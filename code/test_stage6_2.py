# code/test_stage6_2.py

from data_loader import load_data
from payment_options import build_payment_options
from payment_eligibility import filter_eligible_payment_options


TEST_REQUEST_ID = "request_01"
TEST_USER_ID = "user_01"


data = load_data()

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

print("=" * 55)
print("STAGE 6.2 — PAYMENT ELIGIBILITY FILTER")
print("=" * 55)

print(f"Request ID:              {TEST_REQUEST_ID}")
print(f"User ID:                 {TEST_USER_ID}")
print(f"All options:             {len(options)}")
print(
    "Allowed methods:         "
    f"{profile['payment_methods_user_will_consider']}"
)
print(
    "Max installment months:  "
    f"{profile['max_installment_months']}"
)
print(f"Eligible options:        {len(eligible_options)}")
print()

for option in eligible_options:
    print(
        f"{option.payment_option_id} | "
        f"{option.payment_method} | "
        f"{option.number_of_payments} payments | "
        f"{option.total_payable_amount}"
    )

print("=" * 55)