"""Synthetic data generator for SaaSGuard.

Generates 5 inter-correlated tables that produce real churn signal.
The key design principle is **profile-based generation**: each customer is
assigned a hidden churn destiny at birth that deterministically shapes all
their downstream behaviour. This ensures the data is causally coherent —
a model trained on it will learn genuine signal, not noise.

Churn destiny probabilities by plan tier:
    ┌──────────────────┬─────────┬────────┬────────────┬──────┐
    │ Profile          │ starter │ growth │ enterprise │ free │
    ├──────────────────┼─────────┼────────┼────────────┼──────┤
    │ early_churner    │  25%    │   8%   │    3%      │  40% │
    │ mid_churner      │  20%    │  12%   │    5%      │  20% │
    │ retained         │  45%    │  65%   │   75%      │  25% │
    │ expanded         │  10%    │  15%   │   17%      │  15% │
    └──────────────────┴─────────┴────────┴────────────┴──────┘

Usage: python -m src.infrastructure.data_generation.generate_synthetic_data
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from faker import Faker

# ── Constants ─────────────────────────────────────────────────────────────────

RANDOM_SEED = 42
N_CUSTOMERS = 5_500  # +500 free-tier customers added in v0.9.1
OUTPUT_DIR = Path("data/raw")

PLAN_TIERS: list[str] = ["free", "starter", "growth", "enterprise"]
PLAN_TIER_WEIGHTS = [0.09, 0.46, 0.32, 0.13]  # market distribution (renormalised for free)

# MRR ranges (min, max) per plan tier
MRR_RANGES: dict[str, tuple[float, float]] = {
    "free": (0.0, 0.0),  # freemium — zero MRR
    "starter": (500.0, 2_000.0),
    "growth": (2_000.0, 8_000.0),
    "enterprise": (8_000.0, 50_000.0),
}

# Destiny probabilities per plan tier [early_churner, mid_churner, retained, expanded]
DESTINY_PROBS: dict[str, list[float]] = {
    "free": [0.40, 0.20, 0.25, 0.15],  # high early churn, 15% convert to paid
    "starter": [0.25, 0.20, 0.45, 0.10],
    "growth": [0.08, 0.12, 0.65, 0.15],
    "enterprise": [0.03, 0.05, 0.75, 0.17],
}
DESTINY_LABELS = ["early_churner", "mid_churner", "retained", "expanded"]

INDUSTRIES = [
    "FinTech",
    "HealthTech",
    "LegalTech",
    "HR Tech",
    "EdTech",
    "InsurTech",
    "PropTech",
    "RetailTech",
]

EVENT_TYPES = [
    "evidence_upload",
    "monitoring_run",
    "report_view",
    "user_invite",
    "integration_connect",
    "api_call",
    "premium_feature_trial",
    "feature_limit_hit",
]

# Events per week by destiny (Poisson lambda)
EVENTS_PER_WEEK: dict[str, float] = {
    "early_churner": 1.5,
    "mid_churner": 5.0,
    "retained": 10.0,
    "expanded": 12.0,
}

# integration_connect count in first 30 days (Poisson lambda)
INTEGRATION_LAMBDA: dict[str, float] = {
    "early_churner": 0.4,
    "mid_churner": 1.8,
    "retained": 4.0,
    "expanded": 4.5,
}

# feature_limit_hit event weight per destiny (probability within event draw)
# Free/expanded customers hit limits most; all paid tiers get minimal noise
FEATURE_LIMIT_HIT_WEIGHT: dict[str, float] = {
    "free_expanded": 0.20,  # free customers who will convert
    "free_retained": 0.08,  # free customers who stay free
    "free_early_churner": 0.02,  # free customers who churn
    "free_mid_churner": 0.02,
    "paid": 0.01,  # all paid tiers — noise level
}

# Support ticket rate (tickets per month, Poisson lambda)
TICKET_RATE_NORMAL: dict[str, float] = {
    "early_churner": 1.5,
    "mid_churner": 0.8,
    "retained": 0.3,
    "expanded": 0.2,
    "free_churner": 0.5,  # proxy for free early/mid churners
    "free_other": 0.1,  # proxy for free retained/expanded
}
# Rate during pre-churn spike window (last 60 days before churn)
TICKET_RATE_SPIKE: dict[str, float] = {
    "early_churner": 4.0,
    "mid_churner": 2.5,
}

# Priority distributions (low, medium, high, critical) per destiny
TICKET_PRIORITY_PROBS: dict[str, list[float]] = {
    "early_churner": [0.10, 0.25, 0.45, 0.20],
    "mid_churner": [0.15, 0.35, 0.35, 0.15],
    "retained": [0.40, 0.40, 0.15, 0.05],
    "expanded": [0.50, 0.35, 0.12, 0.03],
}

# Topic distribution per destiny
TICKET_TOPICS_CHURNER = ["onboarding", "integration", "billing", "compliance", "feature_request"]
TICKET_TOPICS_CHURNER_PROBS = [0.30, 0.35, 0.20, 0.10, 0.05]
TICKET_TOPICS_HEALTHY = ["compliance", "feature_request", "onboarding", "integration", "billing"]
TICKET_TOPICS_HEALTHY_PROBS = [0.35, 0.35, 0.15, 0.10, 0.05]
# Expanded customers skew heavily toward feature_request — asking for capabilities above their tier
TICKET_TOPICS_EXPANDED = ["feature_request", "compliance", "onboarding", "integration", "billing"]
TICKET_TOPICS_EXPANDED_PROBS = [0.55, 0.25, 0.10, 0.07, 0.03]

# compliance_gap_score Beta distribution params (alpha, beta) per destiny
COMPLIANCE_GAP_BETA: dict[str, tuple[float, float]] = {
    "early_churner": (6.0, 2.0),  # mean ~0.75
    "mid_churner": (3.5, 3.0),  # mean ~0.54
    "retained": (1.5, 6.0),  # mean ~0.20
    "expanded": (1.2, 7.0),  # mean ~0.15
}

# Signup date range — customers joined over the last 3 years
SIGNUP_START = date(2023, 1, 1)
SIGNUP_END = date(2025, 9, 30)

# Decay sigmoid parameters
DECAY_K = 0.1
DECAY_WINDOW_DAYS = 45


# ── RNG setup ─────────────────────────────────────────────────────────────────

rng = np.random.default_rng(RANDOM_SEED)
fake = Faker()
Faker.seed(RANDOM_SEED)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _uuid() -> str:
    # Generate 16 random bytes and build a UUID (int64 max is 2^63, so split into two halves)
    hi = int(rng.integers(0, 2**63))
    lo = int(rng.integers(0, 2**63))
    return str(uuid.UUID(int=(hi << 64) | lo))


def _random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=int(rng.integers(0, delta)))


def _decay_multiplier(day_offset: int, churn_days_away: int) -> float:
    """Sigmoid decay: approaches 0 near churn, 1 far from churn.

    Args:
        day_offset: Days since signup for the event being generated.
        churn_days_away: Days remaining until churn_date from signup.

    Returns:
        Float in (0, 1] — multiplier applied to the Poisson event rate.
    """
    t = day_offset - (churn_days_away - DECAY_WINDOW_DAYS)
    return float(1.0 / (1.0 + np.exp(DECAY_K * t)))


# ── Customer generation ───────────────────────────────────────────────────────


def _generate_customers() -> pd.DataFrame:
    """Generate 5,000 customers with churn destiny and derived churn_date.

    Business Context:
        Each customer's plan_tier determines their churn destiny probability.
        The destiny drives all downstream data generation — this is the
        root of all causal relationships in the dataset.

    Returns:
        DataFrame with columns matching the customers schema in data_dictionary.md.
    """
    rows = []
    for _ in range(N_CUSTOMERS):
        plan_tier = rng.choice(PLAN_TIERS, p=PLAN_TIER_WEIGHTS)
        destiny = rng.choice(DESTINY_LABELS, p=DESTINY_PROBS[plan_tier])

        signup_date = _random_date(SIGNUP_START, SIGNUP_END)

        # MRR: free tier is always 0; expanded paid customers get top 30% of tier range
        mrr_min, mrr_max = MRR_RANGES[plan_tier]
        if plan_tier == "free":
            mrr = 0.0
        elif destiny == "expanded":
            mrr_min = mrr_min + 0.70 * (mrr_max - mrr_min)
            mrr = round(float(rng.uniform(mrr_min, mrr_max)), 2)
        else:
            mrr = round(float(rng.uniform(mrr_min, mrr_max)), 2)

        # Churn date
        churn_date = None
        if destiny == "early_churner":
            churn_days = int(rng.integers(30, 91))
            churn_date = signup_date + timedelta(days=churn_days)
        elif destiny == "mid_churner":
            churn_days = int(rng.integers(91, 366))
            churn_date = signup_date + timedelta(days=churn_days)

        # Cap churn_date to not exceed today (right-censoring)
        today = date(2026, 3, 14)
        if churn_date and churn_date > today:
            churn_date = None  # Treat as still active (censored)

        # Upgrade date — analogous to churn_date for the expansion signal
        upgrade_date = None
        if destiny == "expanded":
            upgrade_days = int(rng.integers(120, 541))
            candidate = signup_date + timedelta(days=upgrade_days)
            upgrade_date = candidate if candidate <= today else None

        rows.append(
            {
                "customer_id": _uuid(),
                "industry": rng.choice(INDUSTRIES),
                "plan_tier": plan_tier,
                "signup_date": signup_date.isoformat(),
                "mrr": mrr,
                "churn_date": churn_date.isoformat() if churn_date else None,
                "upgrade_date": upgrade_date.isoformat() if upgrade_date else None,
                "_destiny": destiny,  # internal — dropped before output
            }
        )

    return pd.DataFrame(rows)


# ── Usage events generation ───────────────────────────────────────────────────


def _generate_usage_events(customers: pd.DataFrame) -> pd.DataFrame:
    """Generate usage events with realistic decay patterns for churners.

    Business Context:
        Usage decay is the primary churn signal. For churning customers,
        a sigmoid decay multiplier reduces event frequency in the weeks
        approaching churn_date, simulating the disengagement pattern
        observed in real B2B SaaS data (Vitally, 2025).

    Args:
        customers: DataFrame with _destiny and churn_date columns.

    Returns:
        DataFrame matching the usage_events schema.
    """
    today = date(2026, 3, 14)
    all_events: list[dict[str, Any]] = []

    for _, cust in customers.iterrows():
        destiny: str = cust["_destiny"]
        signup = date.fromisoformat(cust["signup_date"])
        churn_date = date.fromisoformat(cust["churn_date"]) if pd.notna(cust["churn_date"]) else None
        end_date = churn_date if churn_date else today
        total_days = (end_date - signup).days
        if total_days <= 0:
            continue

        base_lambda_week = EVENTS_PER_WEEK[destiny]
        churn_days_total = total_days if churn_date else None

        # First 30 days: integration_connect burst (activation window)
        n_integrations = int(rng.poisson(INTEGRATION_LAMBDA[destiny]))
        for _ in range(n_integrations):
            day_offset = int(rng.integers(0, min(30, total_days)))
            ts = signup + timedelta(days=day_offset)
            score = float(np.clip(rng.normal(0.55 + 0.15 * (destiny != "early_churner"), 0.1), 0.0, 1.0))
            all_events.append(
                {
                    "event_id": _uuid(),
                    "customer_id": cust["customer_id"],
                    "timestamp": f"{ts}T{rng.integers(8, 20):02d}:{rng.integers(0, 60):02d}:00",
                    "event_type": "integration_connect",
                    "feature_adoption_score": round(score, 4),
                }
            )

        # Week-by-week event generation
        week = 0
        day_offset = 0
        while day_offset < total_days:
            week_days = min(7, total_days - day_offset)

            # Apply decay for churners
            if churn_date and churn_days_total:
                mult = _decay_multiplier(day_offset + week_days // 2, churn_days_total)
            else:
                mult = 1.0

            # Gradual adoption score trajectory
            if destiny in ("retained", "expanded"):
                # Score climbs from ~0.5 to ~0.8 over first 90 days, then stabilises
                progress = min(day_offset / 90.0, 1.0)
                score_mean = 0.50 + 0.30 * progress
            elif destiny == "mid_churner":
                # Peaks at day 60, then decays
                progress = min(day_offset / 60.0, 1.0)
                peak = 0.55 + 0.10 * progress
                decay = max(0.0, (day_offset - 60) / total_days * 0.40)
                score_mean = peak - decay
            else:  # early_churner
                # Starts low, decays fast
                score_mean = max(0.05, 0.40 - (day_offset / total_days) * 0.35)

            n_events = int(rng.poisson(base_lambda_week * (week_days / 7) * mult))
            for _ in range(n_events):
                event_day = day_offset + int(rng.integers(0, week_days))
                ts = signup + timedelta(days=event_day)
                if ts > end_date:
                    continue
                score = float(np.clip(rng.normal(score_mean, 0.08), 0.0, 1.0))

                # Event type weighted by destiny — churners skew toward passive events
                # 8-type weights: evidence_upload, monitoring_run, report_view,
                #   user_invite, integration_connect, api_call,
                #   premium_feature_trial, feature_limit_hit
                plan_tier_local = cust["plan_tier"]
                is_free = plan_tier_local == "free"
                if is_free and destiny == "expanded":
                    weights = [0.15, 0.10, 0.15, 0.08, 0.08, 0.12, 0.12, 0.20]
                elif is_free and destiny == "retained":
                    weights = [0.20, 0.15, 0.20, 0.10, 0.10, 0.09, 0.08, 0.08]
                elif is_free:  # free early/mid churner
                    weights = [0.28, 0.12, 0.30, 0.08, 0.06, 0.12, 0.02, 0.02]
                elif destiny in ("early_churner", "mid_churner"):
                    weights = [0.30, 0.14, 0.35, 0.05, 0.05, 0.10, 0.01, 0.00]
                elif destiny == "expanded":
                    weights = [0.18, 0.17, 0.12, 0.10, 0.10, 0.17, 0.15, 0.01]
                else:  # retained paid
                    weights = [0.19, 0.24, 0.15, 0.10, 0.10, 0.20, 0.02, 0.00]
                # Normalise (weights may not sum to exactly 1.0 due to edits)
                w_arr = [float(w) for w in weights]
                w_sum = sum(w_arr)
                w_arr = [w / w_sum for w in w_arr]

                event_type = rng.choice(EVENT_TYPES, p=w_arr)
                all_events.append(
                    {
                        "event_id": _uuid(),
                        "customer_id": cust["customer_id"],
                        "timestamp": f"{ts}T{rng.integers(8, 20):02d}:{rng.integers(0, 60):02d}:00",
                        "event_type": event_type,
                        "feature_adoption_score": round(score, 4),
                    }
                )

            day_offset += week_days
            week += 1

    return pd.DataFrame(all_events)


# ── Support tickets generation ────────────────────────────────────────────────


def _generate_support_tickets(customers: pd.DataFrame) -> pd.DataFrame:
    """Generate support tickets with a pre-churn spike for churning customers.

    Business Context:
        Spike in high/critical tickets in the 60 days before churn is a
        statistically significant churn predictor. This mirrors the pattern
        documented in stakeholder-notes.md: reactive support correlates
        strongly with cancellation.

    Args:
        customers: DataFrame with _destiny and churn_date columns.

    Returns:
        DataFrame matching the support_tickets schema.
    """
    today = date(2026, 3, 14)
    tickets: list[dict[str, Any]] = []

    for _, cust in customers.iterrows():
        destiny: str = cust["_destiny"]
        signup = date.fromisoformat(cust["signup_date"])
        churn_date = date.fromisoformat(cust["churn_date"]) if pd.notna(cust["churn_date"]) else None
        end_date = churn_date if churn_date else today

        priorities = ["low", "medium", "high", "critical"]
        is_churner = destiny in ("early_churner", "mid_churner")

        # Normal ticket period
        spike_start = churn_date - timedelta(days=60) if churn_date else None
        normal_end = spike_start if spike_start else end_date

        normal_months = max(0, (normal_end - signup).days // 30)
        rate = TICKET_RATE_NORMAL[destiny]
        n_normal = int(rng.poisson(rate * normal_months))

        for _ in range(n_normal):
            ticket_date = signup + timedelta(days=int(rng.integers(0, max(1, (normal_end - signup).days))))
            priority = rng.choice(priorities, p=TICKET_PRIORITY_PROBS[destiny])
            if destiny == "expanded":
                topic = rng.choice(TICKET_TOPICS_EXPANDED, p=TICKET_TOPICS_EXPANDED_PROBS)
            elif is_churner:
                topic = rng.choice(TICKET_TOPICS_CHURNER, p=TICKET_TOPICS_CHURNER_PROBS)
            else:
                topic = rng.choice(TICKET_TOPICS_HEALTHY, p=TICKET_TOPICS_HEALTHY_PROBS)
            res_hours = int(rng.integers(4, 48) if is_churner else rng.integers(2, 16))
            tickets.append(
                {
                    "ticket_id": _uuid(),
                    "customer_id": cust["customer_id"],
                    "created_date": ticket_date.isoformat(),
                    "priority": priority,
                    "resolution_time": res_hours,
                    "topic": topic,
                }
            )

        # Pre-churn spike (last 60 days)
        if churn_date and is_churner:
            assert spike_start is not None  # set above when churn_date is truthy
            spike_days = (churn_date - spike_start).days
            spike_months = max(1, spike_days // 30)
            n_spike = int(rng.poisson(TICKET_RATE_SPIKE[destiny] * spike_months))
            for _ in range(n_spike):
                ticket_date = spike_start + timedelta(days=int(rng.integers(0, spike_days)))
                # Spike tickets skew high/critical
                priority = rng.choice(priorities, p=[0.05, 0.15, 0.50, 0.30])
                topic = rng.choice(TICKET_TOPICS_CHURNER, p=TICKET_TOPICS_CHURNER_PROBS)
                res_hours = int(rng.integers(18, 72))
                tickets.append(
                    {
                        "ticket_id": _uuid(),
                        "customer_id": cust["customer_id"],
                        "created_date": ticket_date.isoformat(),
                        "priority": priority,
                        "resolution_time": res_hours,
                        "topic": topic,
                    }
                )

    return pd.DataFrame(tickets)


# ── GTM opportunities generation ──────────────────────────────────────────────


def _generate_gtm_opportunities(customers: pd.DataFrame) -> pd.DataFrame:
    """Generate sales opportunities, primarily for retained/expanded customers.

    Business Context:
        Churning customers should not have many open expansion opportunities —
        when they do, it creates a revenue-at-risk flag for the GTM domain.
        The `expanded` destiny always has an open opp.

    Args:
        customers: DataFrame with _destiny column.

    Returns:
        DataFrame matching the gtm_opportunities schema.
    """
    today = date(2026, 3, 14)
    opps: list[dict[str, Any]] = []
    sales_owners = [fake.name() for _ in range(20)]

    for _, cust in customers.iterrows():
        destiny: str = cust["_destiny"]
        signup = date.fromisoformat(cust["signup_date"])
        churn_date = date.fromisoformat(cust["churn_date"]) if pd.notna(cust["churn_date"]) else None
        mrr = float(cust["mrr"])

        # How many opps to create
        if destiny == "expanded":
            n_opps = int(rng.integers(1, 3))
        elif destiny == "retained":
            n_opps = int(rng.poisson(0.6))  # ~60% have at least one opp
        elif destiny == "mid_churner":
            n_opps = int(rng.poisson(0.15))  # ~15% — revenue at risk flag
        else:  # early_churner
            n_opps = int(rng.poisson(0.05))

        for _ in range(n_opps):
            tenure_days = (today - signup).days if not churn_date else (churn_date - signup).days
            opp_day = int(rng.integers(min(30, tenure_days // 2), max(31, tenure_days)))
            close_date = signup + timedelta(days=opp_day)

            # Stage: expanded get open stages, churners more likely closed_lost
            if destiny == "expanded":
                stage = rng.choice(
                    ["proposal", "closed_won", "qualification"],
                    p=[0.40, 0.45, 0.15],
                )
            elif destiny == "retained":
                stage = rng.choice(
                    ["closed_won", "proposal", "qualification", "prospecting", "closed_lost"],
                    p=[0.50, 0.20, 0.15, 0.10, 0.05],
                )
            else:
                stage = rng.choice(
                    ["closed_lost", "prospecting", "qualification", "proposal", "closed_won"],
                    p=[0.55, 0.20, 0.15, 0.07, 0.03],
                )

            amount = round(mrr * rng.uniform(6.0, 18.0), 2)
            opportunity_type = "expansion" if destiny == "expanded" else "new_business"
            opps.append(
                {
                    "opp_id": _uuid(),
                    "customer_id": cust["customer_id"],
                    "stage": stage,
                    "close_date": close_date.isoformat(),
                    "amount": amount,
                    "sales_owner": rng.choice(sales_owners),
                    "opportunity_type": opportunity_type,
                }
            )

    return pd.DataFrame(opps)


# ── Risk signals generation ───────────────────────────────────────────────────


def _generate_risk_signals(customers: pd.DataFrame) -> pd.DataFrame:
    """Generate one risk signal row per customer using Beta distributions.

    Business Context:
        compliance_gap_score is a strong churn predictor — customers who
        haven't addressed compliance gaps are more likely to disengage.
        Beta distribution gives a bounded, skewed distribution appropriate
        for a score (0–1) with profile-specific mean/variance.

    Args:
        customers: DataFrame with _destiny column.

    Returns:
        DataFrame matching the risk_signals schema.
    """
    rows = []
    for _, cust in customers.iterrows():
        destiny: str = cust["_destiny"]
        alpha, beta = COMPLIANCE_GAP_BETA[destiny]
        gap_score = float(np.clip(rng.beta(alpha, beta), 0.0, 1.0))

        # Vendor risk flags: Poisson with higher rate for churning customers
        vendor_lambda = {"early_churner": 3.5, "mid_churner": 2.0, "retained": 0.5, "expanded": 0.3}
        vendor_flags = int(rng.poisson(vendor_lambda[destiny]))

        rows.append(
            {
                "customer_id": cust["customer_id"],
                "compliance_gap_score": round(gap_score, 4),
                "vendor_risk_flags": vendor_flags,
            }
        )

    return pd.DataFrame(rows)


# ── Expansion outreach log generation ─────────────────────────────────────────


def _generate_expansion_outreach_log(customers: pd.DataFrame) -> pd.DataFrame:
    """Generate a feedback-loop log of CS outreach to expansion-propensity candidates.

    Business Context:
        The outreach log enables model lift measurement after CS intervention.
        It simulates real-world post-outreach outcomes so the feedback loop
        integration tests have meaningful data to validate against.

    Sampling logic:
        - ~300 'expanded'-destiny customers are selected as contacts.
        - Each gets 1-2 outreach rows (multi-touch campaigns).
        - propensity_at_outreach ~ Beta(7, 3) (mean ≈ 0.70) — top decile scoring.
        - outcome mix: upgraded 30%, active 50%, no_response 20%.

    Args:
        customers: DataFrame with _destiny and customer_id columns.

    Returns:
        DataFrame with columns: outreach_id, customer_id, contacted_date,
        propensity_at_outreach, outreach_channel, outcome.
    """
    today = date(2026, 3, 14)
    expanded_ids = customers[customers["_destiny"] == "expanded"]["customer_id"].tolist()

    # Sample ~300 contacts (or all if fewer)
    n_contacts = min(300, len(expanded_ids))
    contacted_ids = rng.choice(expanded_ids, size=n_contacts, replace=False).tolist()

    channels = ["email", "phone", "in_app", "qbr"]
    channel_weights = [0.40, 0.30, 0.20, 0.10]
    outcomes_upgraded = ["upgraded", "active", "no_response"]
    outcome_weights_upgraded = [0.30, 0.50, 0.20]

    rows = []
    for cid in contacted_ids:
        n_touchpoints = int(rng.integers(1, 3))  # 1 or 2 outreach rows
        for _ in range(n_touchpoints):
            # propensity_at_outreach ~ Beta(7, 3), mean ≈ 0.70
            propensity = float(np.clip(rng.beta(7.0, 3.0), 0.0, 1.0))
            # contacted_date: within last 12 months
            days_ago = int(rng.integers(0, 365))
            contacted_date = today - timedelta(days=days_ago)
            channel = rng.choice(channels, p=channel_weights)
            outcome = rng.choice(outcomes_upgraded, p=outcome_weights_upgraded)
            rows.append(
                {
                    "outreach_id": _uuid(),
                    "customer_id": cid,
                    "contacted_date": contacted_date.isoformat(),
                    "propensity_at_outreach": round(propensity, 4),
                    "outreach_channel": channel,
                    "outcome": outcome,
                }
            )

    return pd.DataFrame(rows)


# ── Main ──────────────────────────────────────────────────────────────────────


def generate_all(output_dir: Path = OUTPUT_DIR) -> None:
    """Generate all 5 synthetic tables and write to CSV.

    Args:
        output_dir: Directory to write CSV files to. Defaults to data/raw/.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating customers...")
    customers = _generate_customers()

    print("Generating usage events (this takes ~30s)...")
    usage_events = _generate_usage_events(customers)

    print("Generating support tickets...")
    support_tickets = _generate_support_tickets(customers)

    print("Generating GTM opportunities...")
    gtm_opportunities = _generate_gtm_opportunities(customers)

    print("Generating risk signals...")
    risk_signals = _generate_risk_signals(customers)

    print("Generating expansion outreach log...")
    outreach_log = _generate_expansion_outreach_log(customers)

    # Drop internal _destiny column before writing
    customers_out = customers.drop(columns=["_destiny"])

    # Write CSVs
    customers_out.to_csv(output_dir / "customers.csv", index=False)
    usage_events.to_csv(output_dir / "usage_events.csv", index=False)
    support_tickets.to_csv(output_dir / "support_tickets.csv", index=False)
    gtm_opportunities.to_csv(output_dir / "gtm_opportunities.csv", index=False)
    risk_signals.to_csv(output_dir / "risk_signals.csv", index=False)
    outreach_log.to_csv(output_dir / "expansion_outreach_log.csv", index=False)

    # ── Summary stats (visual QA) ─────────────────────────────────────────────
    print("\n── Generation Summary ──────────────────────────────────────────")
    print(f"  customers:              {len(customers_out):>8,}")
    print(f"  usage_events:           {len(usage_events):>8,}")
    print(f"  support_tickets:        {len(support_tickets):>8,}")
    print(f"  gtm_opportunities:      {len(gtm_opportunities):>8,}")
    print(f"  risk_signals:           {len(risk_signals):>8,}")
    print(f"  expansion_outreach_log: {len(outreach_log):>8,}")

    free_count = len(customers[customers["plan_tier"] == "free"])
    print(f"\n── Free-tier customers: {free_count:,} ({free_count / len(customers_out):.1%})")

    print("\n── Churn rates by plan tier ────────────────────────────────────")
    for tier in PLAN_TIERS:
        tier_df = customers[customers["plan_tier"] == tier]
        churn_rate = tier_df["churn_date"].notna().mean()
        print(f"  {tier:<12}: {churn_rate:.1%}  (n={len(tier_df)})")

    print("\n── Avg events per customer by destiny ──────────────────────────")
    event_counts = usage_events.groupby("customer_id").size()
    customers_with_counts = customers.copy()
    customers_with_counts["event_count"] = customers_with_counts["customer_id"].map(event_counts).fillna(0)
    for destiny in DESTINY_LABELS:
        subset = customers_with_counts[customers_with_counts["_destiny"] == destiny]
        avg = subset["event_count"].mean()
        print(f"  {destiny:<16}: {avg:>6.1f} avg events")

    print("\n── Avg compliance_gap_score by destiny ─────────────────────────")
    customers_with_risk = customers.merge(risk_signals, on="customer_id")
    for destiny in DESTINY_LABELS:
        subset = customers_with_risk[customers_with_risk["_destiny"] == destiny]
        avg = subset["compliance_gap_score"].mean()
        print(f"  {destiny:<16}: {avg:.3f}")

    print("\n✅ All files written to", output_dir)


if __name__ == "__main__":
    generate_all()
