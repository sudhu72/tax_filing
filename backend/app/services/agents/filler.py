from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from app.models.workflow import FieldEntry


class FormFillerAgent:
    def fill_form(self, form_path: Path, fields: list[FieldEntry], output_path: Path) -> Path:
        reader = PdfReader(str(form_path))
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        form_fields = reader.get_fields()
        if not form_fields:
            raise ValueError("Uploaded form PDF is not fillable (no AcroForm fields found).")

        target_names = list(form_fields.keys())
        value_map = self._build_pdf_value_map(fields, target_names)

        for page in writer.pages:
            writer.update_page_form_field_values(page, value_map)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as f:
            writer.write(f)
        return output_path

    def _build_pdf_value_map(self, fields: list[FieldEntry], target_names: list[str]) -> dict[str, str]:
        result: dict[str, str] = {}
        for entry in fields:
            if not entry.value:
                continue
            target = entry.target_field_name or self._best_match(entry.key, target_names)
            if target:
                result[target] = entry.value
        return result

    def _best_match(self, source_key: str, candidates: list[str]) -> str | None:
        best_name: str | None = None
        best_score = 0.0
        for candidate in candidates:
            score = SequenceMatcher(None, source_key.lower(), candidate.lower()).ratio()
            if score > best_score:
                best_score = score
                best_name = candidate
        return best_name if best_score >= 0.35 else None
