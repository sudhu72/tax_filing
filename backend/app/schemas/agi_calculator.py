"""Schemas for AGI and medical deduction calculator."""
from pydantic import BaseModel, Field


class AGIInputs(BaseModel):
    """User inputs for AGI calculation."""

    filing_status: str = Field(default="Single", description="Filing status")
    # Income (Form 1040 lines)
    wages: float = Field(default=0, ge=0, description="Wages, salaries, tips (W-2 box 1)")
    taxable_interest: float = Field(default=0, ge=0)
    ordinary_dividends: float = Field(default=0, ge=0)
    taxable_ira: float = Field(default=0, ge=0)
    taxable_pension: float = Field(default=0, ge=0)
    taxable_social_security: float = Field(default=0, ge=0)
    capital_gain_loss: float = Field(default=0, description="Net capital gain (positive) or loss (negative)")
    sch_c_income: float = Field(default=0, ge=0, description="Schedule C / self-employment")
    other_income: float = Field(default=0, ge=0)
    # Adjustments to income
    educator_expenses: float = Field(default=0, ge=0)
    ira_deduction: float = Field(default=0, ge=0)
    student_loan_interest: float = Field(default=0, ge=0)
    other_adjustments: float = Field(default=0, ge=0)
    # Medical (for 7.5% test)
    medical_expenses: float = Field(default=0, ge=0, description="Total medical/dental before reimbursement")
    medical_insurance_reimbursement: float = Field(default=0, ge=0)


class DocumentSource(BaseModel):
    """Document needed for a specific line item."""

    line: str
    description: str
    documents: list[str]
    value: float = 0


class AGICalculatorResponse(BaseModel):
    """Result of AGI calculation with medical deduction analysis."""

    total_income: float
    adjustments: float
    agi: float
    medical_7p5_threshold: float
    medical_expenses_net: float
    medical_deductible: float
    medical_exceeds_threshold: bool
    document_sources: list[DocumentSource]
    message: str | None = None
