"""
IRS Forms service: fetches latest tax form PDFs from irs.gov.
Uses the official IRS pub directory: https://www.irs.gov/pub/irs-pdf/
"""
from __future__ import annotations

from pathlib import Path

import httpx

from app.core.config import settings

IRS_PUB_BASE = "https://www.irs.gov/pub/irs-pdf"

# Curated list of common tax forms - form_id -> (display_name, filename)
# Filename is the IRS pub path segment
IRS_FORMS = {
    "f1040": ("Form 1040 - Individual Income Tax Return", "f1040.pdf"),
    "f1040s1": ("Schedule 1 - Additional Income", "f1040s1.pdf"),
    "f1040s2": ("Schedule 2 - Additional Taxes", "f1040s2.pdf"),
    "f1040s3": ("Schedule 3 - Additional Credits", "f1040s3.pdf"),
    "f1040sa": ("Schedule A - Itemized Deductions", "f1040sa.pdf"),
    "f1040sb": ("Schedule B - Interest and Dividends", "f1040sb.pdf"),
    "f1040sc": ("Schedule C - Business Income", "f1040sc.pdf"),
    "f1040sd": ("Schedule D - Capital Gains", "f1040sd.pdf"),
    "f1040se": ("Schedule E - Rental Income", "f1040se.pdf"),
    "i1040gi": ("Form 1040 Instructions", "i1040gi.pdf"),
    "fw9": ("Form W-9 - TIN and Certification", "fw9.pdf"),
    "iw9": ("Form W-9 Instructions", "iw9.pdf"),
    "fw4": ("Form W-4 - Withholding Certificate", "fw4.pdf"),
    "fw2": ("Form W-2 - Wage and Tax Statement", "fw2.pdf"),
    "fw7": ("Form W-7 - ITIN Application", "fw7.pdf"),
    "f1040es": ("Form 1040-ES - Estimated Tax", "f1040es.pdf"),
    "f4506t": ("Form 4506-T - Transcript Request", "f4506t.pdf"),
    "f9465": ("Form 9465 - Installment Agreement", "f9465.pdf"),
    "fss4": ("Form SS-4 - EIN Application", "fss4.pdf"),
}


def list_forms() -> list[dict[str, str]]:
    """Return list of available forms with id, name, and download URL."""
    return [
        {"id": fid, "name": name, "url": f"{IRS_PUB_BASE}/{filename}"}
        for fid, (name, filename) in IRS_FORMS.items()
    ]


def get_form(form_id: str) -> tuple[bytes, str] | None:
    """
    Fetch form PDF from IRS. Returns (pdf_bytes, filename) or None if not found.
    """
    if form_id not in IRS_FORMS:
        return None
    _, filename = IRS_FORMS[form_id]
    url = f"{IRS_PUB_BASE}/{filename}"
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.content, filename
    except Exception:
        return None


def download_and_cache(form_id: str) -> Path | None:
    """
    Fetch form from IRS and save to local cache. Returns path to cached file or None.
    """
    result = get_form(form_id)
    if not result:
        return None
    pdf_bytes, filename = result
    cache_dir = Path(settings.data_dir) / "irs_forms"
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / filename
    path.write_bytes(pdf_bytes)
    return path
