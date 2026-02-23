"""
Recommendation engine: suggests credits, deductions, and CPA-like tips
based on extracted tax data.
"""
from __future__ import annotations

from typing import Any

from app.services.credits import credit_engine
from app.services.tax_engine import tax_engine


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


class RecommendationService:
    def _field_map(self, fields: list[dict]) -> dict[str, float]:
        return {f.get("key", ""): _parse(f.get("value", 0)) for f in fields}

    def get_recommendations(
        self,
        fields: list[dict],
        tax_result: dict[str, Any] | None = None,
        schema_name: str = "",
    ) -> list[dict[str, str]]:
        recs: list[dict[str, str]] = []
        m = self._field_map(fields)

        if tax_result is None:
            tax_result = tax_engine.compute(fields)

        agi = tax_result.get("agi", 0)
        itemized = tax_result.get("itemized_deduction", 0)
        std = tax_result.get("standard_deduction", 0)
        deduction_used = tax_result.get("deduction_used", "standard")

        # Itemization suggestion
        if deduction_used == "standard" and itemized > 0 and itemized > std:
            recs.append({
                "type": "optimization",
                "title": "Consider itemizing",
                "detail": f"Your estimated itemized deductions (${itemized:,.0f}) exceed the standard deduction (${std:,.0f}). Switching to itemized may reduce taxable income.",
            })
        elif deduction_used == "itemized" and std >= itemized:
            recs.append({
                "type": "optimization",
                "title": "Standard deduction may be better",
                "detail": f"The standard deduction (${std:,.0f}) is greater than your itemized total. Using standard typically simplifies filing.",
            })

        # Medical floor reminder
        medical = m.get("medical_expenses", 0)
        if medical > 0 and medical < 0.075 * agi:
            recs.append({
                "type": "informational",
                "title": "Medical expense deduction",
                "detail": f"Medical expenses are deductible only above 7.5% of AGI (${0.075 * agi:,.0f}). Your expenses (${medical:,.0f}) are below that threshold.",
            })

        # EITC eligibility hint
        if agi < 60_000:
            recs.append({
                "type": "credit",
                "title": "Check Earned Income Tax Credit",
                "detail": "Your income may qualify for the EITC. Answer the EITC questions to see if you're eligible. Qualifying children increase the credit.",
            })

        # Saver's credit for low/moderate income
        if agi < 41_000:
            recs.append({
                "type": "credit",
                "title": "Saver's Credit",
                "detail": "Contributions to IRAs or ABLE accounts may qualify for the Retirement Savings Contributions Credit if income is within limits.",
            })

        # Elderly/disabled credit
        recs.append({
            "type": "credit",
            "title": "Credit for Elderly or Disabled",
            "detail": "If you're 65+ or retired on permanent disability with taxable disability income, you may qualify for Schedule R credit.",
        })

        # Dependent care
        recs.append({
            "type": "credit",
            "title": "Child and Dependent Care Credit",
            "detail": "If you paid for care for a child under 13 or a disabled dependent so you could work, you may claim this credit.",
        })

        # Home modification (medical)
        if "schedule-a" in schema_name.lower() or "schedule_a" in schema_name:
            recs.append({
                "type": "deduction",
                "title": "Home modifications for disability",
                "detail": "Chair lifts, ramps, grab bars, and similar modifications may qualify as medical expenses. Cost minus increase in home value is deductible (subject to 7.5% AGI floor).",
            })

        return recs

    def estimate_credits(
        self,
        fields: list[dict],
        tax_result: dict[str, Any],
        num_qualifying_children: int = 0,
        num_dependents_under_17: int = 0,
        dependent_care_expenses: float = 0,
        num_dep_care_individuals: int = 0,
        elderly_or_disabled: bool = False,
        has_disability_income: bool = False,
    ) -> dict[str, Any]:
        return credit_engine.compute_all(
            agi=tax_result.get("agi", 0),
            taxable_income=tax_result.get("taxable_income", 0),
            tax_before_credits=tax_result.get("tax_before_credits", 0),
            filing_status=tax_result.get("filing_status", "Single"),
            num_qualifying_children=num_qualifying_children,
            num_dependents_under_17=num_dependents_under_17,
            dependent_care_expenses=dependent_care_expenses,
            num_dep_care_individuals=num_dep_care_individuals,
            elderly_or_disabled=elderly_or_disabled,
            has_disability_income=has_disability_income,
        )


recommendation_service = RecommendationService()
