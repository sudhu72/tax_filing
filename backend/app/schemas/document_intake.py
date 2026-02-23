"""Schemas for document intake (bulk upload, classify, extract)."""
from pydantic import BaseModel, Field


class ClassifiedDocResponse(BaseModel):
    """Single classified document result."""

    filename: str
    doc_type: str
    confidence: float
    extracted_fields: dict[str, float | str] = Field(default_factory=dict)
    message: str | None = None


class DocumentIntakeResponse(BaseModel):
    """Response after processing uploaded documents."""

    documents: list[ClassifiedDocResponse]
    merged_fields: dict[str, float]
    message: str = ""
