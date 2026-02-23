from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.models.workflow import FieldEntry, RunState, RunStatus
from app.schemas.workflow import TaxCalculateRequest
from app.services.agents.filler import FormFillerAgent
from app.services.agents.irs_instructions import IRSInstructionsAgent
from app.services.agents.scanner import DocumentScannerAgent
from app.services.agents.transformer import DataTransformerAgent
from app.services.credits import credit_engine
from app.services.recommendations import recommendation_service
from app.services.storage import storage_service
from app.services.submission import submission_service
from app.services.tax_engine import tax_engine


class WorkflowOrchestrator:
    def __init__(self) -> None:
        self.scanner = DocumentScannerAgent()
        self.irs_instructions = IRSInstructionsAgent()
        self.transformer = DataTransformerAgent()
        self.filler = FormFillerAgent()

    def create_run(self, identity_bytes: bytes, identity_name: str, form_bytes: bytes, form_name: str, schema_name: str) -> RunState:
        run_id = str(uuid4())
        run_dir = storage_service.run_dir(run_id)
        (run_dir / "identity.pdf").write_bytes(identity_bytes)
        (run_dir / "form.pdf").write_bytes(form_bytes)

        state = RunState(
            run_id=run_id,
            identity_filename=identity_name,
            form_filename=form_name,
            schema_name=schema_name,
            logs=["Run initialized"],
        )
        storage_service.save_state(state)
        return state

    def scan(self, run_id: str) -> RunState:
        state = storage_service.load_state(run_id)
        run_dir = storage_service.run_dir(run_id)
        markdown = self.scanner.scan_to_markdown(run_dir / "identity.pdf")
        md_path = storage_service.save_markdown(run_id, markdown)

        state.extracted_markdown_path = str(md_path)
        state.status = RunStatus.scanned
        state.logs.append("Document scanner agent finished OCR/text extraction")
        storage_service.save_state(state)
        return state

    def load_instructions(self, run_id: str, form_codes: list[str]) -> RunState:
        state = storage_service.load_state(run_id)
        if not form_codes:
            raise ValueError("At least one IRS form code is required")

        instructions = self.irs_instructions.fetch_instructions(form_codes=form_codes)
        state.irs_instructions = instructions
        state.status = RunStatus.instructions_loaded
        state.logs.append(f"IRS instructions agent fetched guidance for: {', '.join(form_codes)}")
        storage_service.save_state(state)
        return state

    def transform(self, run_id: str) -> RunState:
        state = storage_service.load_state(run_id)
        if not state.extracted_markdown_path:
            raise ValueError("Scan step not completed")

        markdown = Path(state.extracted_markdown_path).read_text(encoding="utf-8")
        schema = storage_service.load_schema(state.schema_name)
        instruction_context = "\n".join([f"{item.form_code}: {item.summary}" for item in state.irs_instructions])
        transformed = self.transformer.transform_markdown(markdown, schema, instruction_context=instruction_context)

        state.transformed_fields = transformed
        state.status = RunStatus.transformed
        state.logs.append("Data transformer agent mapped markdown to structured fields")
        storage_service.save_state(state)
        return state

    def review(self, run_id: str, reviewed_fields: list[FieldEntry]) -> RunState:
        state = storage_service.load_state(run_id)
        state.reviewed_fields = reviewed_fields
        saved = storage_service.save_fields(run_id, [f.model_dump() for f in reviewed_fields])
        state.reviewed_fields_path = str(saved)
        state.status = RunStatus.reviewed
        state.logs.append("Human review completed and approved fields were saved")
        storage_service.save_state(state)
        return state

    def fill(self, run_id: str) -> RunState:
        state = storage_service.load_state(run_id)
        if not state.reviewed_fields:
            raise ValueError("Review step required before fill")

        run_dir = storage_service.run_dir(run_id)
        output_path = run_dir / "completed.pdf"
        self.filler.fill_form(run_dir / "form.pdf", state.reviewed_fields, output_path)

        state.completed_pdf_path = str(output_path)
        state.status = RunStatus.filled
        state.logs.append("Form filler agent generated a completed PDF")
        storage_service.save_state(state)
        return state

    def submit(self, run_id: str, email_to: str | None, webhook_url: str | None) -> tuple[RunState, list]:
        state = storage_service.load_state(run_id)
        if not state.completed_pdf_path:
            raise ValueError("Fill step required before submit")

        results = []
        pdf_path = Path(state.completed_pdf_path)
        if email_to:
            results.append(submission_service.send_email(email_to, pdf_path, run_id))
        if webhook_url:
            results.append(submission_service.post_webhook(webhook_url, run_id, pdf_path))

        state.submission_results = results
        state.status = RunStatus.submitted
        state.logs.append("Submission step completed")
        storage_service.save_state(state)
        return state, results

    def get_state(self, run_id: str) -> RunState:
        return storage_service.load_state(run_id)

    def calculate_tax(self, run_id: str, request: TaxCalculateRequest | None = None) -> RunState:
        state = storage_service.load_state(run_id)
        fields = state.reviewed_fields if state.reviewed_fields else state.transformed_fields
        if not fields:
            raise ValueError("No field data. Complete transform or review first.")
        fd = [f.model_dump() if hasattr(f, "model_dump") else f for f in fields]
        tax_result = tax_engine.compute(fd)
        req = request or TaxCalculateRequest()
        credit_result = credit_engine.compute_all(
            agi=tax_result["agi"],
            taxable_income=tax_result["taxable_income"],
            tax_before_credits=tax_result["tax_before_credits"],
            filing_status=tax_result["filing_status"],
            num_qualifying_children=req.num_qualifying_children,
            num_dependents_under_17=req.num_dependents_under_17,
            dependent_care_expenses=req.dependent_care_expenses,
            num_dep_care_individuals=req.num_dep_care_individuals,
            elderly_or_disabled=req.elderly_or_disabled,
            has_disability_income=req.has_disability_income,
        )
        tax_result["credits"] = credit_result
        state.tax_result = tax_result
        state.recommendations = recommendation_service.get_recommendations(
            fd, tax_result, state.schema_name
        )
        state.logs.append("Tax engine computed AGI, deductions, tax, and credits")
        storage_service.save_state(state)
        return state

    def get_recommendations(self, run_id: str) -> RunState:
        state = storage_service.load_state(run_id)
        fields = state.reviewed_fields if state.reviewed_fields else state.transformed_fields
        if not fields:
            raise ValueError("No field data. Complete transform or review first.")
        fd = [f.model_dump() if hasattr(f, "model_dump") else f for f in fields]
        if not state.tax_result:
            state.tax_result = tax_engine.compute(fd)
        state.recommendations = recommendation_service.get_recommendations(
            fd, state.tax_result, state.schema_name
        )
        state.logs.append("Recommendations generated")
        storage_service.save_state(state)
        return state


workflow_orchestrator = WorkflowOrchestrator()
