from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.schemas.workflow import CreateRunResponse, InstructionsRequest, ReviewFieldsRequest, StepResponse, SubmitRequest, SubmitResponse, TaxCalculateRequest
from app.services.orchestrator import workflow_orchestrator
from app.services.validation import validate_fields

router = APIRouter()


@router.post("/runs", response_model=CreateRunResponse)
async def create_run(
    identity_document: UploadFile = File(...),
    tax_form: UploadFile | None = File(default=None),
    irs_form_id: str | None = Form(default=None),
    schema_name: str = Form(default="w9.yaml"),
) -> CreateRunResponse:
    try:
        if irs_form_id:
            from app.services.irs_forms import get_form
            result = get_form(irs_form_id)
            if not result:
                raise HTTPException(status_code=400, detail=f"IRS form '{irs_form_id}' not found or unavailable")
            form_bytes, filename = result
            form_name = filename
        elif tax_form and tax_form.filename:
            form_bytes = await tax_form.read()
            form_name = tax_form.filename or "form.pdf"
        else:
            raise HTTPException(status_code=400, detail="Provide either a tax form upload or an IRS form ID (irs_form_id)")
        state = workflow_orchestrator.create_run(
            identity_bytes=await identity_document.read(),
            identity_name=identity_document.filename or "identity.pdf",
            form_bytes=form_bytes,
            form_name=form_name,
            schema_name=schema_name,
        )
        return CreateRunResponse(run_id=state.run_id, status=state.status.value)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/scan", response_model=StepResponse)
def scan(run_id: str) -> StepResponse:
    try:
        return StepResponse(run=workflow_orchestrator.scan(run_id))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/transform", response_model=StepResponse)
def transform(run_id: str) -> StepResponse:
    try:
        return StepResponse(run=workflow_orchestrator.transform(run_id))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/instructions", response_model=StepResponse)
def load_instructions(run_id: str, request: InstructionsRequest) -> StepResponse:
    try:
        return StepResponse(run=workflow_orchestrator.load_instructions(run_id, request.form_codes))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/runs/{run_id}/review", response_model=StepResponse)
def review(run_id: str, request: ReviewFieldsRequest) -> StepResponse:
    try:
        fd = [f.model_dump() if hasattr(f, "model_dump") else f for f in request.fields]
        validation_issues = validate_fields(fd)
        run = workflow_orchestrator.review(run_id, request.fields)
        if validation_issues:
            run.errors = list(run.errors) + validation_issues
        return StepResponse(run=run)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/fill", response_model=StepResponse)
def fill(run_id: str) -> StepResponse:
    try:
        return StepResponse(run=workflow_orchestrator.fill(run_id))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/submit", response_model=SubmitResponse)
def submit(run_id: str, request: SubmitRequest) -> SubmitResponse:
    try:
        run, results = workflow_orchestrator.submit(run_id, request.email_to, str(request.webhook_url) if request.webhook_url else None)
        return SubmitResponse(run=run, results=results)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/tax/calculate", response_model=StepResponse)
def calculate_tax(run_id: str, request: TaxCalculateRequest | None = None) -> StepResponse:
    try:
        return StepResponse(run=workflow_orchestrator.calculate_tax(run_id, request))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs/{run_id}/recommendations", response_model=StepResponse)
def get_recommendations(run_id: str) -> StepResponse:
    try:
        return StepResponse(run=workflow_orchestrator.get_recommendations(run_id))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs/{run_id}", response_model=StepResponse)
def get_run(run_id: str) -> StepResponse:
    try:
        return StepResponse(run=workflow_orchestrator.get_state(run_id))
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}/download")
def download_pdf(run_id: str) -> FileResponse:
    try:
        state = workflow_orchestrator.get_state(run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not state.completed_pdf_path:
        raise HTTPException(status_code=400, detail="Completed form not available yet")

    path = Path(state.completed_pdf_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Completed form file not found")

    return FileResponse(path=path, filename=f"{run_id}_completed.pdf", media_type="application/pdf")
