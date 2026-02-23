"""
Validation service: sanity checks on extracted/reviewed tax data.
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


def validate_fields(fields: list[dict]) -> list[str]:
    """Return list of warning/error messages. Empty if all ok."""
    issues: list[str] = []
    m = {f.get("key", ""): f.get("value") for f in fields}

    # SSN format
    ssn = str(m.get("ssn", "")).strip().replace("-", "")
    if ssn and (len(ssn) != 9 or not ssn.isdigit()):
        issues.append("SSN should be 9 digits (with or without dashes)")

    # Wages non-negative
    wages = _parse(m.get("wages", 0))
    if wages < 0:
        issues.append("Wages cannot be negative")

    # AGI-like sanity: total income vs adjustments
    total_inc = wages + _parse(m.get("taxable_interest", 0)) + _parse(m.get("ordinary_dividends", 0))
    if total_inc > 10_000_000:
        issues.append("Total income is unusually high; verify figures")

    # Medical 7.5% floor reminder
    medical = _parse(m.get("medical_expenses", 0))
    if medical > 0 and total_inc > 0:
        threshold = 0.075 * total_inc
        if medical < threshold:
            issues.append(f"Medical expenses (${medical:,.0f}) are below 7.5% AGI threshold (${threshold:,.0f})")

    return issues
