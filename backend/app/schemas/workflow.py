from __future__ import annotations

from pydantic import BaseModel, HttpUrl

from app.models.workflow import FieldEntry, RunState, SubmissionResult


class CreateRunResponse(BaseModel):
    run_id: str
    status: str


class ReviewFieldsRequest(BaseModel):
    fields: list[FieldEntry]


class InstructionsRequest(BaseModel):
    form_codes: list[str]


class SubmitRequest(BaseModel):
    email_to: str | None = None
    webhook_url: HttpUrl | None = None


class StepResponse(BaseModel):
    run: RunState


class SubmitResponse(BaseModel):
    run: RunState
    results: list[SubmissionResult]


class TaxCalculateRequest(BaseModel):
    num_qualifying_children: int = 0
    num_dependents_under_17: int = 0
    dependent_care_expenses: float = 0
    num_dep_care_individuals: int = 0
    elderly_or_disabled: bool = False
    has_disability_income: bool = False
