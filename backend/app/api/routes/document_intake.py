"""Document intake API: upload docs, classify, extract, merge."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.document_intake import (
    ClassifiedDocResponse,
    DocumentFeedbackRequest,
    DocumentFeedbackResponse,
    DocumentFeedbackStatsResponse,
    DocumentIntakeResponse,
    DocumentTestResponse,
)
from app.services.agents.document_classifier import DocumentClassifierAgent
from app.services.agents.scanner import DocumentScannerAgent, ALLOWED_EXTENSIONS

router = APIRouter()
scanner = DocumentScannerAgent()
classifier = DocumentClassifierAgent()

MAX_FILES = 50
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def _classify_upload(upload: UploadFile, data: bytes) -> ClassifiedDocResponse:
    markdown = scanner.scan_bytes_to_markdown(data, upload.filename or "uploaded-file")
    result = classifier.classify_and_extract(upload.filename or "uploaded-file", markdown)
    doc_message = None
    if result.doc_type == "Government ID":
        doc_message = "Government ID detected. Ignored for tax extraction."
    elif result.doc_type == "Unknown":
        doc_message = "Low-confidence classification. No tax fields extracted."
    return ClassifiedDocResponse(
        filename=result.filename,
        doc_type=result.doc_type,
        confidence=result.confidence,
        extracted_fields=result.extracted_fields,
        message=doc_message,
        raw_snippet=result.raw_snippet,
        score_breakdown=result.score_breakdown,
    )


@router.post("/process", response_model=DocumentIntakeResponse)
async def process_documents(files: list[UploadFile] = File(...)) -> DocumentIntakeResponse:
    """
    Upload documents and receipts (PDF, Excel, images). The agent classifies each
    document (W-2, 1099-INT, medical receipt, etc.) and extracts values for tax forms.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one file")

    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_FILES} files allowed")

    documents: list[ClassifiedDocResponse] = []
    merged: dict[str, float] = {}

    for upload in files:
        if not upload.filename:
            continue

        ext = "." + upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            documents.append(
                ClassifiedDocResponse(
                    filename=upload.filename,
                    doc_type="Skipped",
                    confidence=0,
                    message=f"Unsupported format. Use: {', '.join(ALLOWED_EXTENSIONS)}",
                )
            )
            continue

        try:
            data = await upload.read()
            if len(data) > MAX_FILE_SIZE:
                documents.append(
                    ClassifiedDocResponse(
                        filename=upload.filename,
                        doc_type="Skipped",
                        confidence=0,
                        message=f"File too large (max {MAX_FILE_SIZE // (1024*1024)} MB)",
                    )
                )
                continue

            doc = _classify_upload(upload, data)
            documents.append(doc)

            # Merge into combined fields (sum numeric values)
            for key, val in doc.extracted_fields.items():
                if isinstance(val, (int, float)):
                    merged[key] = merged.get(key, 0) + float(val)

        except Exception as e:
            documents.append(
                ClassifiedDocResponse(
                    filename=upload.filename,
                    doc_type="Error",
                    confidence=0,
                    message=str(e),
                )
            )

    msg = f"Processed {len([d for d in documents if d.doc_type not in ('Skipped', 'Error')])} documents. "
    if merged:
        msg += f"Extracted values for: {', '.join(merged.keys())}."
    else:
        msg += "No values extracted. Check document formats and try again."

    return DocumentIntakeResponse(
        documents=documents,
        merged_fields=merged,
        message=msg,
    )


@router.post("/test", response_model=DocumentTestResponse)
async def test_document(file: UploadFile = File(...)) -> DocumentTestResponse:
    """
    Test classification on a single document and return detailed output,
    including confidence scores and extracted tax-relevant fields.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Use: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_FILE_SIZE // (1024*1024)} MB)")

    doc = _classify_upload(file, data)
    relevant = sorted(list(doc.extracted_fields.keys()))
    return DocumentTestResponse(document=doc, tax_relevant_fields=relevant)


@router.post("/feedback", response_model=DocumentFeedbackResponse)
def submit_feedback(request: DocumentFeedbackRequest) -> DocumentFeedbackResponse:
    """Accept user feedback (approve/override) to improve classifier weights."""
    count = classifier.record_feedback(
        predicted_doc_type=request.predicted_doc_type,
        corrected_doc_type=request.corrected_doc_type,
        filename=request.filename,
        raw_snippet=request.raw_snippet or "",
        accepted=request.accepted,
    )
    if request.accepted and request.predicted_doc_type == request.corrected_doc_type:
        msg = f"Feedback saved: reinforced {request.corrected_doc_type}."
    else:
        msg = (
            f"Feedback saved: adjusted model from {request.predicted_doc_type} "
            f"toward {request.corrected_doc_type}."
        )
    return DocumentFeedbackResponse(ok=True, message=msg, feedback_count=count)


@router.get("/feedback/stats", response_model=DocumentFeedbackStatsResponse)
def get_feedback_stats() -> DocumentFeedbackStatsResponse:
    stats = classifier.get_feedback_stats()
    return DocumentFeedbackStatsResponse(**stats)
