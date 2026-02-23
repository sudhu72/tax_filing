from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.agi_calculator import router as agi_calculator_router
from app.api.routes.document_intake import router as document_intake_router
from app.api.routes.irs_forms import router as irs_forms_router
from app.api.routes.workflow import router as workflow_router
from app.core.config import settings
from app.middleware.audit import log_request, setup_audit_log

setup_audit_log(settings.data_dir)

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    run_id = None
    if "/runs/" in path:
        parts = path.split("/runs/")
        if len(parts) > 1 and parts[1]:
            run_id = parts[1].split("/")[0]  # first path segment after runs/
    log_request(request.method, path, run_id=run_id, status=response.status_code)
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workflow_router, prefix="/api/workflow", tags=["workflow"])
app.include_router(irs_forms_router, prefix="/api/irs-forms", tags=["irs-forms"])
app.include_router(agi_calculator_router, prefix="/api/agi-calculator", tags=["agi-calculator"])
app.include_router(document_intake_router, prefix="/api/document-intake", tags=["document-intake"])


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}
