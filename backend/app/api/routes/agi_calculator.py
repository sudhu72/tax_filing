"""AGI and medical deduction calculator API."""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas.agi_calculator import AGICalculatorResponse, AGIInputs, DocumentSource

router = APIRouter()

# Document guidance: what forms/documents are needed for each income/adjustment line
DOCUMENT_GUIDE: list[tuple[str, str, list[str]]] = [
    ("wages", "Wages, salaries, tips", ["W-2 (all employers)"]),
    ("taxable_interest", "Taxable interest", ["1099-INT"]),
    ("ordinary_dividends", "Ordinary dividends", ["1099-DIV"]),
    ("taxable_ira", "Taxable IRA distributions", ["1099-R", "IRA distribution statements"]),
    ("taxable_pension", "Taxable pensions/annuities", ["1099-R", "Pension statements"]),
    ("taxable_social_security", "Taxable Social Security", ["SSA-1099", "RRB-1099"]),
    ("capital_gain_loss", "Capital gains or losses", ["1099-B", "Brokerage statements", "Schedule D"]),
    ("sch_c_income", "Self-employment income", ["1099-NEC", "Schedule C", "Business records"]),
    ("other_income", "Other income", ["1099-MISC", "1099-K", "Gambling winnings (W-2G)", "Other income statements"]),
    ("educator_expenses", "Educator expenses", ["School receipts", "Employment records"]),
    ("ira_deduction", "IRA deduction", ["Form 5498", "IRA contribution records"]),
    ("student_loan_interest", "Student loan interest", ["1098-E"]),
    ("other_adjustments", "Other adjustments", ["Health savings account (HSA)", "Moving expense forms", "Other adjustment records"]),
]


@router.post("/calculate", response_model=AGICalculatorResponse)
def calculate_agi(inputs: AGIInputs) -> AGICalculatorResponse:
    """
    Calculate AGI and determine if medical expenses exceed 7.5% of AGI.
    Disability-related medical expenses (equipment, home modifications, premiums, etc.)
    are deductible only to the extent they exceed 7.5% of AGI.
    """
    total_income = (
        inputs.wages
        + inputs.taxable_interest
        + inputs.ordinary_dividends
        + inputs.taxable_ira
        + inputs.taxable_pension
        + inputs.taxable_social_security
        + inputs.capital_gain_loss
        + inputs.sch_c_income
        + inputs.other_income
    )
    adjustments = (
        inputs.educator_expenses
        + inputs.ira_deduction
        + inputs.student_loan_interest
        + inputs.other_adjustments
    )
    agi = max(0, total_income - adjustments)
    medical_threshold = 0.075 * agi
    medical_net = max(0, inputs.medical_expenses - inputs.medical_insurance_reimbursement)
    medical_deductible = max(0, medical_net - medical_threshold)
    exceeds = medical_net > medical_threshold

    # Build document sources with actual values
    values_map = {
        "wages": inputs.wages,
        "taxable_interest": inputs.taxable_interest,
        "ordinary_dividends": inputs.ordinary_dividends,
        "taxable_ira": inputs.taxable_ira,
        "taxable_pension": inputs.taxable_pension,
        "taxable_social_security": inputs.taxable_social_security,
        "capital_gain_loss": inputs.capital_gain_loss,
        "sch_c_income": inputs.sch_c_income,
        "other_income": inputs.other_income,
        "educator_expenses": inputs.educator_expenses,
        "ira_deduction": inputs.ira_deduction,
        "student_loan_interest": inputs.student_loan_interest,
        "other_adjustments": inputs.other_adjustments,
    }

    document_sources = [
        DocumentSource(line=line, description=desc, documents=docs, value=values_map.get(line, 0))
        for line, desc, docs in DOCUMENT_GUIDE
    ]

    # Add medical document guidance
    document_sources.append(
        DocumentSource(
            line="medical_expenses",
            description="Medical and dental expenses (disability-related: equipment, home modifications, premiums)",
            documents=[
                "Medical/dental receipts",
                "Insurance premium statements",
                "Prescription records",
                "Disability equipment invoices (wheelchairs, ramps, grab bars, etc.)",
                "Home modification costs (minus increase in home value)",
            ],
            value=inputs.medical_expenses,
        )
    )

    message = None
    if medical_net > 0 and not exceeds:
        message = (
            f"Your medical expenses (${medical_net:,.0f}) do not exceed 7.5% of AGI (${medical_threshold:,.0f}). "
            "Amount above 7.5% of AGI is deductible if you itemize."
        )
    elif exceeds:
        message = (
            f"Your medical expenses (${medical_net:,.0f}) exceed 7.5% of AGI (${medical_threshold:,.0f}). "
            f"You may deduct ${medical_deductible:,.0f} on Schedule A if you itemize."
        )

    return AGICalculatorResponse(
        total_income=round(total_income, 2),
        adjustments=round(adjustments, 2),
        agi=round(agi, 2),
        medical_7p5_threshold=round(medical_threshold, 2),
        medical_expenses_net=round(medical_net, 2),
        medical_deductible=round(medical_deductible, 2),
        medical_exceeds_threshold=exceeds,
        document_sources=document_sources,
        message=message,
    )
