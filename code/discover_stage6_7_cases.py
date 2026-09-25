from datetime import date, timedelta
from decimal import Decimal

import pandas as pd

from build_events import events_df_to_raw_events
from payment_decision import build_payment_decision
from payment_options import build_payment_options
from project_recurrence import project_recurring
from reconcile import build_cash_events


DATASET_DIR = "dataset"
FORECAST_HORIZON_DAYS = 90


def main():
    profiles_df = pd.read_csv(
        f"{DATASET_DIR}/financial_profiles.csv"
    )

    events_df = pd.read_csv(
        f"{DATASET_DIR}/financial_events.csv"
    )

    requests_df = pd.read_csv(
        f"{DATASET_DIR}/requests.csv"
    )

    payment_options_df = pd.read_csv(
        f"{DATASET_DIR}/request_payment_options.csv"
    )

    # ---------------------------------------------------------------
    # Build all cash events once.
    # ---------------------------------------------------------------

    print("=" * 80)
    print("STAGE 6.7 — REAL REQUEST CASE DISCOVERY")
    print("=" * 80)
    print()
    print("Building resolved cash events...")

    raw_events = events_df_to_raw_events(events_df)

    event_layers = build_cash_events(raw_events)

    resolved_events = event_layers["resolved"]

    print(
        f"Resolved cash events: {len(resolved_events)}"
    )
    print()

    # ---------------------------------------------------------------
    # Process every real request.
    # ---------------------------------------------------------------

    requests_with_candidates = []
    requests_without_candidates = []

    method_counts = {
        "full_payment": 0,
        "partial_payment": 0,
        "installments": 0,
        "wait": 0,
    }

    total_generated = 0
    total_unsafe = 0

    for _, request_row in requests_df.iterrows():

        request_id = str(
            request_row["request_id"]
        )

        user_id = str(
            request_row["user_id"]
        )

        profile_matches = profiles_df[
            profiles_df["user_id"].astype(str)
            == user_id
        ]

        if profile_matches.empty:
            continue

        profile_row = profile_matches.iloc[0]

        request_date = date.fromisoformat(
            str(request_row["request_date"])
        )

        requested_amount = Decimal(
            str(request_row["requested_amount"])
        )

        desired_completion_date = date.fromisoformat(
            str(
                request_row[
                    "desired_completion_date"
                ]
            )
        )

        forecast_end = (
            request_date
            + timedelta(
                days=FORECAST_HORIZON_DAYS
            )
        )

        # -----------------------------------------------------------
        # User cash events.
        # -----------------------------------------------------------

        user_events = [
            event
            for event in resolved_events
            if event.user_id == user_id
        ]

        # -----------------------------------------------------------
        # Historical settled events.
        # -----------------------------------------------------------

        historical_events = [
            event
            for event in user_events
            if (
                event.source_status == "settled"
                and event.cash_date <= request_date
            )
        ]

        # -----------------------------------------------------------
        # Real future events.
        # -----------------------------------------------------------

        real_future_events = [
            event
            for event in user_events
            if (
                event.cash_date > request_date
                and event.cash_date <= forecast_end
            )
        ]

        # -----------------------------------------------------------
        # Project recurring events across the 90-day forecast.
        # -----------------------------------------------------------

        projected_events = project_recurring(
            settled_events=historical_events,
            request_date=request_date,
            forecast_end=forecast_end,
            real_future_events=real_future_events,
        )

        simulation_events = (
            user_events
            + projected_events
        )

        # -----------------------------------------------------------
        # Load payment options for this request.
        # -----------------------------------------------------------

        payment_options = build_payment_options(
            payment_options_df=payment_options_df,
            request_id=request_id,
        )

        # -----------------------------------------------------------
        # Complete Stage 6 payment decision.
        # -----------------------------------------------------------

        result = build_payment_decision(
            request_date=request_date,
            requested_amount=requested_amount,
            starting_balance=Decimal(
                str(
                    profile_row[
                        "current_available_balance"
                    ]
                )
            ),
            minimum_balance_to_keep=Decimal(
                str(
                    profile_row[
                        "minimum_balance_to_keep"
                    ]
                )
            ),
            horizon_days=FORECAST_HORIZON_DAYS,
            cash_events=simulation_events,
            payment_options=payment_options,
            payment_methods_user_will_consider=(
                profile_row[
                    "payment_methods_user_will_consider"
                ]
            ),
            max_installment_months=(
                profile_row[
                    "max_installment_months"
                ]
            ),
            allows_partial_payment=bool(
                request_row[
                    "allows_partial_payment"
                ]
            ),
            desired_completion_date=(
                desired_completion_date
            ),
        )

        # -----------------------------------------------------------
        # Record candidate coverage (safe candidates only).
        # -----------------------------------------------------------

        total_generated += len(result.candidates)
        total_unsafe += sum(
            1
            for sim in result.simulations
            if not sim.simulation.safe
        )

        safe_candidates = [
            rc.simulation.candidate
            for rc in result.ranked_candidates
        ]

        if safe_candidates:
            requests_with_candidates.append(
                (
                    request_id,
                    user_id,
                    requested_amount,
                    result,
                )
            )

            for candidate in safe_candidates:
                method = candidate.payment_method

                if method in method_counts:
                    method_counts[method] += 1

        else:
            requests_without_candidates.append(
                (
                    request_id,
                    user_id,
                    requested_amount,
                    result,
                )
            )

    # ---------------------------------------------------------------
    # Summary.
    # ---------------------------------------------------------------

    print("=" * 80)
    print("REQUEST COVERAGE")
    print("=" * 80)

    total_processed = (
        len(requests_with_candidates)
        + len(requests_without_candidates)
    )

    print(
        f"Requests processed:       {total_processed}"
    )

    print(
        "Requests with safe candidates: "
        f"{len(requests_with_candidates)}"
    )

    print(
        "Requests without safe candidates: "
        f"{len(requests_without_candidates)}"
    )

    print(
        f"Total candidates generated:    {total_generated}"
    )

    print(
        f"Candidates failed simulation:  {total_unsafe}"
    )

    print()

    print("=" * 80)
    print("SAFE CANDIDATE METHOD COVERAGE")
    print("=" * 80)

    for method, count in method_counts.items():
        print(
            f"{method:20} {count}"
        )

    print()

    # ---------------------------------------------------------------
    # Show representative cases for each candidate type.
    # ---------------------------------------------------------------

    for method in (
        "full_payment",
        "partial_payment",
        "installments",
        "wait",
    ):
        print("=" * 80)
        print(
            f"{method.upper()} CASES"
        )
        print("=" * 80)

        shown = 0

        for (
            request_id,
            user_id,
            requested_amount,
            result,
        ) in requests_with_candidates:

            matching_candidates = [
                rc.simulation.candidate
                for rc in result.ranked_candidates
                if rc.simulation.candidate.payment_method
                == method
            ]

            if not matching_candidates:
                continue

            for candidate in matching_candidates:

                print(
                    f"{request_id} | "
                    f"{user_id} | "
                    f"requested={requested_amount} | "
                    f"safe={result.amount_safe_to_pay} | "
                    f"earliest="
                    f"{result.earliest_date_for_full_payment} | "
                    f"candidate="
                    f"{candidate.candidate_id}"
                )

                shown += 1

                if shown >= 10:
                    break

            if shown >= 10:
                break

        if shown == 0:
            print("No cases found.")

        print()

    # ---------------------------------------------------------------
    # Show representative no-candidate cases.
    # ---------------------------------------------------------------

    print("=" * 80)
    print("NO CANDIDATE CASES")
    print("=" * 80)

    for (
        request_id,
        user_id,
        requested_amount,
        result,
    ) in requests_without_candidates[:10]:

        print(
            f"{request_id} | "
            f"{user_id} | "
            f"requested={requested_amount} | "
            f"safe={result.amount_safe_to_pay} | "
            f"earliest="
            f"{result.earliest_date_for_full_payment} | "
            f"eligible_options="
            f"{len(result.eligible_options)}"
        )

    print()

    print("=" * 80)
    print("STAGE 6.7 DISCOVERY COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()