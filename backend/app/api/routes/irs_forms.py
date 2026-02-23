from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.services.irs_forms import get_form, list_forms

router = APIRouter()


@router.get("/list")
def list_irs_forms() -> dict:
    """List available IRS tax forms that can be downloaded."""
    forms = list_forms()
    return {"forms": forms, "source": "https://www.irs.gov/pub/irs-pdf/"}


@router.get("/{form_id}/download")
def download_form(form_id: str) -> Response:
    """Download the latest PDF for the given form from IRS."""
    result = get_form(form_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Form '{form_id}' not found or unavailable")
    pdf_bytes, filename = result
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
