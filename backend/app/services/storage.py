from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path

import yaml

from app.core.config import settings
from app.models.workflow import RunState


class StorageService:
    def __init__(self) -> None:
        self.runs_dir = settings.runs_dir
        self.schemas_dir = settings.schemas_dir

    def run_dir(self, run_id: str) -> Path:
        path = self.runs_dir / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def state_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "state.json"

    def save_state(self, state: RunState) -> None:
        state.updated_at = datetime.now(UTC)
        self.state_path(state.run_id).write_text(state.model_dump_json(indent=2), encoding="utf-8")

    def load_state(self, run_id: str) -> RunState:
        path = self.state_path(run_id)
        if not path.exists():
            raise FileNotFoundError(f"Run {run_id} not found")
        return RunState.model_validate_json(path.read_text(encoding="utf-8"))

    def save_markdown(self, run_id: str, text: str) -> Path:
        path = self.run_dir(run_id) / "extracted.md"
        path.write_text(text, encoding="utf-8")
        return path

    def save_fields(self, run_id: str, fields: list[dict]) -> Path:
        path = self.run_dir(run_id) / "fields_reviewed.json"
        path.write_text(json.dumps(fields, indent=2), encoding="utf-8")
        return path

    def load_schema(self, schema_name: str) -> dict:
        path = self.schemas_dir / schema_name
        if not path.exists():
            raise FileNotFoundError(f"Schema {schema_name} not found")
        return yaml.safe_load(path.read_text(encoding="utf-8"))


storage_service = StorageService()
