"""Document intake API: upload docs, classify, extract, merge."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.document_intake import ClassifiedDocResponse, DocumentIntakeResponse
from app.services.agents.document_classifier import DocumentClassifierAgent
from app.services.agents.scanner import DocumentScannerAgent, ALLOWED_EXTENSIONS

router = APIRouter()
scanner = DocumentScannerAgent()
classifier = DocumentClassifierAgent()

MAX_FILES = 50
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


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

            markdown = scanner.scan_bytes_to_markdown(data, upload.filename)
            result = classifier.classify_and_extract(upload.filename, markdown)

            documents.append(
                ClassifiedDocResponse(
                    filename=result.filename,
                    doc_type=result.doc_type,
                    confidence=result.confidence,
                    extracted_fields=result.extracted_fields,
                )
            )

            # Merge into combined fields (sum numeric values)
            for key, val in result.extracted_fields.items():
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
