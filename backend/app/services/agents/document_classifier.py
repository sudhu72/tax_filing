"""Document classifier agent: identifies doc type and extracts tax-relevant fields."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClassifiedDocument:
    """Result of classifying a single document."""

    filename: str
    doc_type: str
    confidence: float
    extracted_fields: dict[str, Any] = field(default_factory=dict)
    raw_snippet: str = ""


# Document type patterns and field extraction rules
DOC_PATTERNS: list[tuple[str, list[str], dict[str, list[str]]]] = [
    (
        "W-2",
        ["w-2", "w2", "wage and tax statement", "form w-2"],
        {
            "wages": ["box 1", "wages tips", "wages salaries", "compensation", "1\\s*[:\\s]"],
            "fed_tax_withheld": ["box 2", "federal income tax", "2\\s*[:\\s]"],
        },
    ),
    (
        "1099-INT",
        ["1099-int", "1099 int", "interest income", "taxable interest"],
        {"taxable_interest": ["interest income", "taxable interest", "1\\s*[:\\s]", "box 1"]},
    ),
    (
        "1099-DIV",
        ["1099-div", "1099 div", "dividends", "ordinary dividends"],
        {
            "ordinary_dividends": ["ordinary dividends", "total ordinary", "1a\\s*[:\\s]"],
            "qualified_dividends": ["qualified dividends", "1b\\s*[:\\s]"],
        },
    ),
    (
        "1099-R",
        ["1099-r", "1099 r", "pension", "ira distribution", "distributions", "annuity"],
        {
            "__1099r_taxable__": ["taxable amount", "taxable distribution", "2a\\s*[:\\s]", "box 2a"],
        },
    ),
    (
        "SSA-1099",
        ["ssa-1099", "ssa 1099", "social security", "benefits paid", "rrb-1099"],
        {"taxable_social_security": ["taxable", "box 5", "benefits", "3\\s*[:\\s]"]},
    ),
    (
        "1099-B",
        ["1099-b", "1099 b", "proceeds", "cost basis", "gain or loss"],
        {"capital_gain_loss": ["proceeds", "gain", "loss", "net proceeds"]},
    ),
    (
        "1099-NEC",
        ["1099-nec", "1099 nec", "nonemployee compensation", "self-employment"],
        {"sch_c_income": ["nonemployee compensation", "1\\s*[:\\s]", "compensation"]},
    ),
    (
        "1098-E",
        ["1098-e", "1098 e", "student loan interest"],
        {"student_loan_interest": ["student loan interest", "1\\s*[:\\s]", "interest paid"]},
    ),
    (
        "Medical/Receipt",
        [
            "medical",
            "physician",
            "doctor",
            "pharmacy",
            "prescription",
            "clinic",
            "hospital",
            "dental",
            "health",
            "receipt",
            "invoice",
            "total due",
            "amount paid",
        ],
        {"medical_expenses": ["total", "amount", "due", "paid", "balance", "subtotal"]},
    ),
]


def _parse_money(text: str) -> float:
    """Extract first dollar amount from text. Handles negative (parens or minus)."""
    # Match $1,234.56 or (1,234.56) or -1234.56
    pattern = r"[\(\$]?\s*-?\s*([\d,]+(?:\.\d{2})?)\s*[\)]?"
    for m in re.finditer(pattern, text):
        s = m.group(1).replace(",", "")
        try:
            val = float(s)
            # If preceded by ( or -, treat as negative
            start = max(0, m.start() - 3)
            snippet = text[start : m.end()]
            if "(" in snippet or snippet.strip().startswith("-"):
                val = -val
            return val
        except ValueError:
            pass
    return 0.0


def _extract_amount_near_keywords(lines: list[str], keywords: list[str]) -> float:
    """Find a line containing a keyword and extract dollar amount from it or next line."""
    text_lower = "\n".join(lines).lower()
    for idx, line in enumerate(lines):
        line_lower = line.lower()
        for kw in keywords:
            if kw.lower() in line_lower or re.search(kw, line_lower, re.I):
                # Try this line first
                amt = _parse_money(line)
                if amt > 0:
                    return amt
                # Try next line
                if idx + 1 < len(lines):
                    amt = _parse_money(lines[idx + 1])
                    if amt > 0:
                        return amt
    # Fallback: any amount in document (for receipts)
    amt = _parse_money(text_lower)
    return amt if amt > 0 else 0.0


class DocumentClassifierAgent:
    """Classifies documents and extracts tax fields."""

    def classify_and_extract(self, filename: str, markdown: str) -> ClassifiedDocument:
        """
        Classify document type and extract relevant fields.
        Returns ClassifiedDocument with doc_type and extracted_fields.
        """
        if not markdown or not markdown.strip():
            return ClassifiedDocument(filename=filename, doc_type="Unknown", confidence=0.0)

        text_upper = markdown.upper()
        text_lower = markdown.lower()
        lines = [l.strip() for l in markdown.splitlines() if l.strip()]

        best_match: tuple[str, float, dict[str, Any]] = ("Other", 0.0, {})

        for doc_type, type_keywords, field_rules in DOC_PATTERNS:
            score = 0.0
            for kw in type_keywords:
                if kw.upper() in text_upper or kw.lower() in text_lower:
                    score += 0.3
                    break

            if score == 0:
                # Check filename
                fn_lower = filename.lower()
                for kw in type_keywords:
                    if kw.replace("-", "") in fn_lower or kw.replace(" ", "") in fn_lower:
                        score += 0.2
                        break

            if score == 0:
                continue

            extracted: dict[str, Any] = {}
            for field_key, key_keywords in field_rules.items():
                val = _extract_amount_near_keywords(lines, key_keywords)
                if val > 0:
                    extracted[field_key] = val

            # Boost score if we extracted something
            if extracted:
                score += 0.4
            score = min(1.0, score)

            if score > best_match[1]:
                best_match = (doc_type, score, extracted)

        doc_type, confidence, extracted = best_match

        # Post-process: 1099-R -> taxable_ira or taxable_pension
        if doc_type == "1099-R" and "__1099r_taxable__" in extracted:
            val = extracted.pop("__1099r_taxable__")
            if "ira" in text_lower or "individual retirement" in text_lower:
                extracted["taxable_ira"] = val
            else:
                extracted["taxable_pension"] = val

        # For medical receipts, sum all amounts if we found multiple
        if doc_type == "Medical/Receipt" and "medical_expenses" in extracted:
            pass  # Already have one amount
        elif doc_type == "Medical/Receipt" and not extracted:
            # Try to get any total-looking amount
            for line in lines:
                if any(
                    w in line.lower()
                    for w in ["total", "amount due", "balance", "paid", "subtotal"]
                ):
                    amt = _parse_money(line)
                    if amt > 0 and amt < 1_000_000:  # Sanity
                        extracted["medical_expenses"] = amt
                        break

        # Snippet for display
        snippet = markdown[:500] if len(markdown) > 500 else markdown

        return ClassifiedDocument(
            filename=filename,
            doc_type=doc_type,
            confidence=confidence,
            extracted_fields=extracted,
            raw_snippet=snippet,
        )
