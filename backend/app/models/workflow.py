from __future__ import annotations

from datetime import datetime, UTC
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    initialized = "initialized"
    scanned = "scanned"
    instructions_loaded = "instructions_loaded"
    transformed = "transformed"
    reviewed = "reviewed"
    filled = "filled"
    submitted = "submitted"
    failed = "failed"


class FieldEntry(BaseModel):
    key: str
    value: str
    description: str = ""
    confidence: float = 0.0
    source_excerpt: str = ""
    target_field_name: str | None = None


class SubmissionResult(BaseModel):
    channel: str
    success: bool
    details: str


class IRSFormInstruction(BaseModel):
    form_code: str
    source_url: str
    summary: str


class RunState(BaseModel):
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: RunStatus = RunStatus.initialized
    errors: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)

    identity_filename: str
    form_filename: str
    schema_name: str

    extracted_markdown_path: str | None = None
    reviewed_fields_path: str | None = None
    completed_pdf_path: str | None = None

    transformed_fields: list[FieldEntry] = Field(default_factory=list)
    reviewed_fields: list[FieldEntry] = Field(default_factory=list)
    submission_results: list[SubmissionResult] = Field(default_factory=list)
    irs_instructions: list[IRSFormInstruction] = Field(default_factory=list)
    tax_result: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[dict[str, str]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
