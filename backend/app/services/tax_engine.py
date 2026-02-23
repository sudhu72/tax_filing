"""
Tax logic engine: computes AGI, deductions, taxable income, tax, and credits.
Uses 2024 figures; update annually for new tax year.
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


def _field_map(fields: list[dict]) -> dict[str, float]:
    return {f.get("key", ""): _parse(f.get("value", 0)) for f in fields}


# 2024 standard deduction amounts
STANDARD_DEDUCTION_2024 = {
    "Single": 14_600,
    "Married Filing Jointly": 29_200,
    "Married Filing Separately": 14_600,
    "Head of Household": 21_900,
    "Qualifying Surviving Spouse": 29_200,
}

# Additional standard deduction for 65+ or blind (2024)
ADDITIONAL_STANDARD_2024 = {
    "Single": 1_950,
    "Married Filing Jointly": 1_550,  # per person
    "Married Filing Separately": 1_550,
    "Head of Household": 1_950,
    "Qualifying Surviving Spouse": 1_550,
}


class TaxEngine:
    def compute(self, fields: list[dict], extras: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Compute full tax scenario from extracted/reviewed fields.
        extras: {"over_65": bool, "blind": bool, "spouse_over_65": bool, "spouse_blind": bool}
        """
        extras = extras or {}
        m = _field_map(fields)
        filing_status = str(extras.get("filing_status") or _get_str(fields, "filing_status") or "Single").strip()
        if filing_status not in STANDARD_DEDUCTION_2024:
            filing_status = "Single"

        # Total income (simplified 1040 lines 1-8)
        total_income = (
            m.get("wages", 0)
            + m.get("taxable_interest", 0)
            + m.get("ordinary_dividends", 0)
            + m.get("taxable_ira", 0)
            + m.get("taxable_pension", 0)
            + m.get("taxable_social_security", 0)
            + m.get("capital_gain_loss", 0)
            + m.get("sch_c_income", 0)
            + m.get("other_income", 0)
        )

        # Adjustments to income
        adjustments = (
            m.get("educator_expenses", 0)
            + m.get("ira_deduction", 0)
            + m.get("student_loan_interest", 0)
            + m.get("other_adjustments", 0)
        )

        agi = max(0, total_income - adjustments)

        # Standard deduction
        std = STANDARD_DEDUCTION_2024[filing_status]
        add_per = ADDITIONAL_STANDARD_2024[filing_status]
        n_add = 0
        if extras.get("over_65"):
            n_add += 1
        if extras.get("blind"):
            n_add += 1
        if filing_status in ("Married Filing Jointly", "Qualifying Surviving Spouse"):
            if extras.get("spouse_over_65"):
                n_add += 1
            if extras.get("spouse_blind"):
                n_add += 1
        std += n_add * add_per

        # Itemized deductions
        use_standard = _get_str(fields, "use_standard_deduction", "true").lower() in ("true", "yes", "1")
        itemized = 0.0
        if not use_standard:
            itemized = self._compute_itemized(m, agi)

        deduction = std if use_standard else max(std, itemized)
        taxable = max(0, agi - deduction)

        # Tax (simplified 2024 brackets - single)
        tax_before_credits = self._tax_from_taxable(taxable, filing_status)

        return {
            "total_income": round(total_income, 2),
            "adjustments": round(adjustments, 2),
            "agi": round(agi, 2),
            "standard_deduction": std,
            "itemized_deduction": round(itemized, 2),
            "deduction_used": "standard" if use_standard and std >= itemized else "itemized",
            "taxable_income": round(taxable, 2),
            "tax_before_credits": round(tax_before_credits, 2),
            "filing_status": filing_status,
        }

    def _compute_itemized(self, m: dict[str, float], agi: float) -> float:
        medical = max(0, m.get("medical_expenses", 0) - m.get("medical_insurance_reimbursement", 0))
        medical_ded = max(0, medical - 0.075 * agi)  # 7.5% floor
        salt_cap = 10_000
        salt = min(
            salt_cap,
            m.get("state_local_income_tax", 0)
            + m.get("state_local_sales_tax", 0)
            + m.get("real_estate_tax", 0),
        )
        interest = m.get("home_mortgage_interest", 0)
        charity = m.get("charitable_cash", 0) + m.get("charitable_non_cash", 0)
        casualty = m.get("casualty_theft_loss", 0)
        other = m.get("other_itemized", 0)
        return medical_ded + salt + interest + charity + casualty + other

    def _tax_from_taxable(self, taxable: float, filing_status: str) -> float:
        # 2024 rates - Single
        brackets = [
            (11_600, 0.10),
            (47_150, 0.12),
            (100_525, 0.22),
            (191_950, 0.24),
            (243_725, 0.32),
            (609_350, 0.35),
            (float("inf"), 0.37),
        ]
        # MFJ roughly double the thresholds
        if filing_status in ("Married Filing Jointly", "Qualifying Surviving Spouse"):
            brackets = [
                (23_200, 0.10),
                (94_300, 0.12),
                (201_050, 0.22),
                (383_900, 0.24),
                (487_450, 0.32),
                (731_200, 0.35),
                (float("inf"), 0.37),
            ]
        elif filing_status == "Head of Household":
            brackets = [
                (16_550, 0.10),
                (63_100, 0.12),
                (100_500, 0.22),
                (191_950, 0.24),
                (243_700, 0.32),
                (609_350, 0.35),
                (float("inf"), 0.37),
            ]

        tax = 0.0
        prev = 0.0
        for threshold, rate in brackets:
            if taxable <= prev:
                break
            bracket_amt = min(taxable, threshold) - prev
            tax += bracket_amt * rate
            prev = threshold
        return tax


def _get_str(fields: list[dict], key: str, default: str = "") -> str:
    for f in fields:
        if f.get("key") == key:
            v = f.get("value", default)
            return str(v).strip() if v is not None else default
    return default


tax_engine = TaxEngine()
