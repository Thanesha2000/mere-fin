# code/payment_eligibility.py

"""
Stage 6.2 — Payment option eligibility filtering.

This module removes payment options that the user is not
willing to consider according to their financial profile.

This stage does NOT:
- simulate payments
- decide affordability
- rank payment options
- choose the final recommendation

It only answers:

    "Which supplied payment options are allowed to be considered?"
"""

from payment_options import PaymentOption


def parse_payment_methods(value):
    """
    Convert the profile's pipe-separated payment-method string
    into a set of normalized method names.

    Example:
        "full_payment|installments"

    becomes:

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


def filter_eligible_payment_options(
    payment_options: list[PaymentOption],
    payment_methods_user_will_consider,
    max_installment_months,
):
    """
    Return payment options that satisfy the user's stated
    payment-method preferences and installment limit.

    Rules:
    1. The payment method must be explicitly accepted.
    2. Installments must respect max_installment_months.
    3. Missing max_installment_months means there is no
       installment-month restriction from the profile.
    """

    allowed_methods = parse_payment_methods(
        payment_methods_user_will_consider
    )

    if max_installment_months is not None:
        try:
            max_installment_months = int(max_installment_months)
        except (TypeError, ValueError):
            max_installment_months = None

    eligible = []

    for option in payment_options:

        # Rule 1:
        # User must explicitly accept this payment method.
        if option.payment_method not in allowed_methods:
            continue

        # Rule 2:
        # Installment duration cannot exceed the user's limit.
        if option.payment_method == "installments":
            if max_installment_months is not None:
                if option.number_of_payments > max_installment_months:
                    continue

        eligible.append(option)

    return eligible