from __future__ import annotations

import re
from typing import Any

from app.models.workflow import FieldEntry


class DataTransformerAgent:
    def transform_markdown(self, markdown: str, schema: dict[str, Any], instruction_context: str = "") -> list[FieldEntry]:
        fields = schema.get("fields", [])
        entries: list[FieldEntry] = []
        text_for_extraction = markdown
        if instruction_context:
            text_for_extraction = f"{markdown}\n\nIRS Guidance Context:\n{instruction_context}"

        for field in fields:
            key = field.get("key", "")
            description = field.get("description", "")
            aliases = field.get("aliases", [])
            default = field.get("default", "")
            value, confidence, excerpt = self._extract_value(text_for_extraction, aliases)
            final_value = value or default
            entries.append(
                FieldEntry(
                    key=key,
                    value=final_value,
                    description=description,
                    confidence=confidence if final_value else 0.0,
                    source_excerpt=excerpt,
                    target_field_name=field.get("target_field_name"),
                )
            )
        return entries

    def _extract_value(self, markdown: str, aliases: list[str]) -> tuple[str, float, str]:
        lines = markdown.splitlines()
        for alias in aliases:
            pattern = re.compile(rf"{re.escape(alias)}\s*[:\-]\s*(.+)", re.IGNORECASE)
            for line in lines:
                match = pattern.search(line)
                if match:
                    value = match.group(1).strip()
                    return value, 0.9, line.strip()

            # Weak fallback: look for the alias and capture nearby line.
            for idx, line in enumerate(lines):
                if alias.lower() in line.lower():
                    nearby = lines[idx + 1].strip() if idx + 1 < len(lines) else line.strip()
                    if nearby:
                        return nearby, 0.5, line.strip()

        return "", 0.0, ""
