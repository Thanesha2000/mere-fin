# code/test_stage6_1.py

from data_loader import load_data
from payment_options import build_payment_options


TEST_REQUEST_ID = "request_01"


data = load_data()

options = build_payment_options(
    data["payment_options"],
    TEST_REQUEST_ID,
)

print("=" * 55)
print("STAGE 6.1 — PAYMENT OPTION LOADER")
print("=" * 55)
print(f"Request ID:       {TEST_REQUEST_ID}")
print(f"Options loaded:   {len(options)}")
print()

for option in options:
    print(option)

print("=" * 55)