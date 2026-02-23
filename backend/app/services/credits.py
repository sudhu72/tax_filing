"""
Tax credit logic: EITC, Child Tax Credit, Dependent Care, Credit for Elderly/Disabled.
Uses 2024 parameters.
"""
from __future__ import annotations

from typing import Any


def _parse(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "").replace("$", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


# 2024 EITC parameters (3+ children)
EITC_2024 = {
    "Single": {"max_credit": 7_830, "phaseout_start": 21_750, "phaseout_end": 57_768},
    "Married Filing Jointly": {"max_credit": 7_830, "phaseout_start": 21_750, "phaseout_end": 63_698},
}

# 2024 CTC: $2,000 per qualifying child, refundable portion up to $1,700
CTC_PER_CHILD = 2_000
CTC_REFUNDABLE_MAX = 1_700

# 2024 Child and Dependent Care Credit: 20-35% of up to $3,000 (1) or $6,000 (2+)
DEP_CARE_MAX_1 = 3_000
DEP_CARE_MAX_2 = 6_000

# Credit for Elderly or Disabled (2024 Schedule R)
ELDERLY_DISABLED_MAX = {"Single": 5_000, "Married Jointly": 7_500}


class CreditEngine:
    def compute_all(
        self,
        agi: float,
        taxable_income: float,
        tax_before_credits: float,
        filing_status: str,
        num_qualifying_children: int = 0,
        num_dependents_under_17: int = 0,
        dependent_care_expenses: float = 0,
        num_dep_care_individuals: int = 0,
        elderly_or_disabled: bool = False,
        has_disability_income: bool = False,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        total_credits = 0.0

        # EITC
        eitc = self._eitc(agi, filing_status, num_qualifying_children)
        if eitc > 0:
            results["earned_income_credit"] = round(eitc, 2)
            total_credits += eitc

        # CTC
        ctc = self._ctc(agi, tax_before_credits, total_credits, num_dependents_under_17)
        if ctc.get("nonrefundable", 0) > 0 or ctc.get("refundable", 0) > 0:
            results["child_tax_credit"] = ctc
            total_credits += ctc.get("nonrefundable", 0) + ctc.get("refundable", 0)

        # Dependent care
        dep_care = self._dependent_care(agi, dependent_care_expenses, num_dep_care_individuals)
        if dep_care > 0:
            results["child_dependent_care_credit"] = round(dep_care, 2)
            total_credits += dep_care

        # Elderly or disabled
        elderly = self._elderly_disabled(agi, filing_status, elderly_or_disabled, has_disability_income)
        if elderly > 0:
            results["credit_elderly_disabled"] = round(elderly, 2)
            total_credits += elderly

        results["total_credits"] = round(total_credits, 2)
        results["tax_after_credits"] = round(max(0, tax_before_credits - total_credits), 2)
        return results

    def _eitc(self, agi: float, filing_status: str, num_children: int) -> float:
        if filing_status not in EITC_2024:
            return 0.0
        p = EITC_2024[filing_status]
        max_credit = p["max_credit"]
        if num_children == 0:
            max_credit = 632
        elif num_children == 1:
            max_credit = 4_213
        elif num_children == 2:
            max_credit = 6_960
        if agi >= p["phaseout_end"]:
            return 0.0
        if agi <= p["phaseout_start"]:
            return max_credit
        phaseout = (agi - p["phaseout_start"]) / (p["phaseout_end"] - p["phaseout_start"])
        return max(0, max_credit * (1 - phaseout))

    def _ctc(
        self,
        agi: float,
        tax_before: float,
        other_nonrefundable: float,
        num_children: int,
    ) -> dict[str, float]:
        credit = num_children * CTC_PER_CHILD
        nonref = min(credit, max(0, tax_before - other_nonrefundable))
        refundable = 0.0
        if num_children > 0 and agi >= 2_500:
            add_refund = min(num_children * CTC_REFUNDABLE_MAX, 0.15 * (agi - 2_500))
            refundable = min(add_refund, credit - nonref)
        return {
            "total": credit,
            "nonrefundable": round(nonref, 2),
            "refundable": round(refundable, 2),
        }

    def _dependent_care(self, agi: float, expenses: float, num_individuals: int) -> float:
        if expenses <= 0 or num_individuals <= 0:
            return 0.0
        max_exp = DEP_CARE_MAX_2 if num_individuals >= 2 else DEP_CARE_MAX_1
        eligible = min(expenses, max_exp)
        if agi <= 15_000:
            pct = 0.35
        else:
            pct = max(0.20, 0.35 - (agi - 15_000) / 2_000 * 0.01)
        return eligible * pct

    def _elderly_disabled(
        self,
        agi: float,
        filing_status: str,
        qualifies: bool,
        has_disability_income: bool,
    ) -> float:
        if not qualifies and not has_disability_income:
            return 0.0
        key = "Married Jointly" if filing_status == "Married Filing Jointly" else "Single"
        base = ELDERLY_DISABLED_MAX.get(key, 5_000)
        if agi >= 17_500 if key == "Single" else 25_000:
            return 0.0
        return min(base, max(0, base - (agi - 7_500) * 0.075))


credit_engine = CreditEngine()
