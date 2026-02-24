"""Schemas for document intake (bulk upload, classify, extract)."""
from pydantic import BaseModel, Field


class ClassifiedDocResponse(BaseModel):
    """Single classified document result."""

    filename: str
    doc_type: str
    confidence: float
    extracted_fields: dict[str, float | str] = Field(default_factory=dict)
    message: str | None = None
    raw_snippet: str | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class DocumentIntakeResponse(BaseModel):
    """Response after processing uploaded documents."""

    documents: list[ClassifiedDocResponse]
    merged_fields: dict[str, float]
    message: str = ""


class DocumentTestResponse(BaseModel):
    """Detailed result for testing a single document."""

    document: ClassifiedDocResponse
    tax_relevant_fields: list[str] = Field(default_factory=list)


class DocumentFeedbackRequest(BaseModel):
    """User feedback to improve classification weights."""

    filename: str
    predicted_doc_type: str
    corrected_doc_type: str
    raw_snippet: str | None = None
    accepted: bool = True


class DocumentFeedbackResponse(BaseModel):
    """Response after feedback ingestion."""

    ok: bool = True
    message: str
    feedback_count: int


class FeedbackConfusionRow(BaseModel):
    predicted: str
    corrected: str
    count: int


class FeedbackClassRow(BaseModel):
    doc_type: str
    count: int


class DocumentFeedbackStatsResponse(BaseModel):
    feedback_count: int
    top_confusions: list[FeedbackConfusionRow] = Field(default_factory=list)
    top_classes: list[FeedbackClassRow] = Field(default_factory=list)
    class_bias: dict[str, float] = Field(default_factory=dict)
