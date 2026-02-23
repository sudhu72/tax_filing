from __future__ import annotations

import re

import httpx

from app.models.workflow import IRSFormInstruction


class IRSInstructionsAgent:
    BASE_URL = "https://www.irs.gov/forms-instructions"

    def fetch_instructions(self, form_codes: list[str]) -> list[IRSFormInstruction]:
        instructions: list[IRSFormInstruction] = []
        for code in form_codes:
            normalized = code.strip().lower().replace(" ", "-")
            url = f"{self.BASE_URL}/about-{normalized}"
            html = self._fetch_html(url)
            summary = self._summarize_html(html)
            instructions.append(
                IRSFormInstruction(
                    form_code=code.upper(),
                    source_url=url,
                    summary=summary,
                )
            )
        return instructions

    def _fetch_html(self, url: str) -> str:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    def _summarize_html(self, html: str) -> str:
        text = re.sub(r"<script.*?>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return "No IRS instruction text extracted."
        return text[:1600]
