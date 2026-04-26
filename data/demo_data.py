"""
Generate synthetic credit union demo dataset and save as parquet files.
"""

import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(42)
OUT = Path(__file__).parent

# ---------------------------------------------------------------------------
# 1. Members
# ---------------------------------------------------------------------------

N_MEMBERS = 2_000

segments = ["Youth", "Young Adult", "Prime", "Established", "Senior"]
seg_weights = [0.08, 0.18, 0.30, 0.28, 0.16]

zip_codes = [
    "47401", "47403", "47408", "47421", "47429",
    "47441", "47448", "47456", "47460", "47462",
]

member_ids = list(range(1, N_MEMBERS + 1))
ages = RNG.integers(16, 88, size=N_MEMBERS)
segments_col = RNG.choice(segments, size=N_MEMBERS, p=seg_weights)
zip_col = RNG.choice(zip_codes, size=N_MEMBERS)

# tenure 0–40 years, weighted toward shorter tenures
tenure_years = np.round(RNG.exponential(scale=8, size=N_MEMBERS).clip(0, 40), 1)

member_since = pd.to_datetime("2026-04-26") - pd.to_timedelta(
    (tenure_years * 365.25).astype(int), unit="D"
)

members = pd.DataFrame(
    {
        "member_id": member_ids,
        "age": ages,
        "tenure_years": tenure_years,
        "segment": segments_col,
        "zip_code": zip_col,
        "member_since": member_since.values,
    }
)

# ---------------------------------------------------------------------------
# 2. Accounts  (avg ~1.6 per member → 3,200)
# ---------------------------------------------------------------------------

N_ACCOUNTS = 3_200

acct_types = ["checking", "savings", "cd", "money_market"]
acct_weights = [0.40, 0.35, 0.14, 0.11]
acct_statuses = ["active", "active", "active", "inactive", "closed"]  # weighted via repeat

# Balance distributions per product type (mean, std) in dollars
balance_params = {
    "checking":     (3_500,  4_000),
    "savings":      (8_000, 12_000),
    "cd":          (22_000, 18_000),
    "money_market": (15_000, 14_000),
}

acct_member_ids = RNG.choice(member_ids, size=N_ACCOUNTS, replace=True)
acct_types_col = RNG.choice(acct_types, size=N_ACCOUNTS, p=acct_weights)
acct_status_col = RNG.choice(["active", "active", "active", "inactive", "closed"], size=N_ACCOUNTS)

balances = np.array([
    max(0, RNG.normal(*balance_params[t]))
    for t in acct_types_col
])
balances = np.round(balances, 2)

# opened_date: between member_since and today
ref_date = pd.Timestamp("2026-04-26")
member_since_map = members.set_index("member_id")["member_since"]
earliest = pd.to_datetime(member_since_map.loc[acct_member_ids].values)
days_available = np.maximum(1, (ref_date - earliest).days.values)
offset_days = (RNG.uniform(0, 1, size=N_ACCOUNTS) * days_available).astype(int)
opened_dates = earliest + pd.to_timedelta(offset_days, unit="D")

accounts = pd.DataFrame(
    {
        "account_id": range(1, N_ACCOUNTS + 1),
        "member_id": acct_member_ids,
        "type": acct_types_col,
        "balance": balances,
        "status": acct_status_col,
        "opened_date": opened_dates,
    }
)

# ---------------------------------------------------------------------------
# 3. Loans  (1,400)
# ---------------------------------------------------------------------------

N_LOANS = 1_400

loan_types = ["auto", "mortgage", "personal", "heloc"]
loan_weights = [0.35, 0.28, 0.25, 0.12]
loan_statuses = ["current", "current", "current", "delinquent", "paid_off", "default"]

# (balance_mean, balance_std, rate_mean, rate_std)
loan_params = {
    "auto":      (18_000,  9_000, 0.0625, 0.010),
    "mortgage":  (185_000, 75_000, 0.0695, 0.008),
    "personal":  ( 8_500,  5_000, 0.1100, 0.020),
    "heloc":     ( 45_000, 30_000, 0.0850, 0.015),
}

loan_member_ids = RNG.choice(member_ids, size=N_LOANS, replace=True)
loan_types_col = RNG.choice(loan_types, size=N_LOANS, p=loan_weights)
loan_status_col = RNG.choice(loan_statuses, size=N_LOANS)

loan_balances = np.array([
    max(0, RNG.normal(loan_params[t][0], loan_params[t][1]))
    for t in loan_types_col
])
loan_rates = np.array([
    round(max(0.01, RNG.normal(loan_params[t][2], loan_params[t][3])), 4)
    for t in loan_types_col
])
loan_balances = np.round(loan_balances, 2)

loan_earliest = pd.to_datetime(member_since_map.loc[loan_member_ids].values)
loan_days = np.maximum(1, (ref_date - loan_earliest).days.values)
loan_offset = (RNG.uniform(0, 1, size=N_LOANS) * loan_days).astype(int)
origination_dates = loan_earliest + pd.to_timedelta(loan_offset, unit="D")

loans = pd.DataFrame(
    {
        "loan_id": range(1, N_LOANS + 1),
        "member_id": loan_member_ids,
        "type": loan_types_col,
        "balance": loan_balances,
        "rate": loan_rates,
        "status": loan_status_col,
        "origination_date": origination_dates,
    }
)

# ---------------------------------------------------------------------------
# 4. Monthly balances — last 6 months, one row per member per month
# ---------------------------------------------------------------------------

months = pd.date_range(end="2026-03-31", periods=6, freq="ME")

rows = []
for month in months:
    # Average balance varies by member with some noise month-to-month
    base_balance = RNG.normal(12_000, 9_000, size=N_MEMBERS).clip(min=0)
    product_counts = RNG.integers(1, 6, size=N_MEMBERS)
    rows.append(
        pd.DataFrame(
            {
                "member_id": member_ids,
                "month": month,
                "avg_balance": np.round(base_balance, 2),
                "product_count": product_counts,
            }
        )
    )

monthly_balances = pd.concat(rows, ignore_index=True)

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

OUT.mkdir(parents=True, exist_ok=True)

members.to_parquet(OUT / "members.parquet", index=False)
accounts.to_parquet(OUT / "accounts.parquet", index=False)
loans.to_parquet(OUT / "loans.parquet", index=False)
monthly_balances.to_parquet(OUT / "monthly_balances.parquet", index=False)

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

for name, df in [
    ("members", members),
    ("accounts", accounts),
    ("loans", loans),
    ("monthly_balances", monthly_balances),
]:
    print(f"\n{'='*50}")
    print(f"  {name}  ({len(df):,} rows)")
    print(f"{'='*50}")
    print(df.dtypes.to_string())
    print(f"\nSample:")
    print(df.head(3).to_string(index=False))
