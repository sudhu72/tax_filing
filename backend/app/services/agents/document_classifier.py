"""Document classifier agent: stronger tax-document classification and extraction."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import settings

@dataclass
class ClassifiedDocument:
    """Result of classifying a single document."""

    filename: str
    doc_type: str
    confidence: float
    extracted_fields: dict[str, Any] = field(default_factory=dict)
    raw_snippet: str = ""
    score_breakdown: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class DocModel:
    """Classification profile for a doc type."""

    name: str
    strong_terms: tuple[str, ...]
    weak_terms: tuple[str, ...]
    negative_terms: tuple[str, ...] = ()
    min_score: float = 0.45


DOC_MODELS: tuple[DocModel, ...] = (
    DocModel(
        name="Government ID",
        strong_terms=("driver license", "driver's license", "dln", "dmv", "class d", "endorsements", "restrictions"),
        weak_terms=("date of birth", "dob", "issued", "expires", "sex", "height", "weight", "eyes"),
        min_score=0.55,
    ),
    DocModel(
        name="W-2",
        strong_terms=("form w-2", "wage and tax statement", "w-2"),
        weak_terms=("box 1", "box 2", "federal income tax withheld", "employer identification number"),
        negative_terms=("1099", "1098", "ssa-1099"),
    ),
    DocModel(
        name="1099-INT",
        strong_terms=("form 1099-int", "1099-int"),
        weak_terms=("interest income", "payer", "box 1", "federal income tax withheld"),
        negative_terms=("w-2", "1099-div", "1099-nec"),
    ),
    DocModel(
        name="1099-DIV",
        strong_terms=("form 1099-div", "1099-div"),
        weak_terms=("ordinary dividends", "qualified dividends", "box 1a", "box 1b"),
        negative_terms=("w-2", "1099-int", "1099-nec"),
    ),
    DocModel(
        name="1099-R",
        strong_terms=("form 1099-r", "1099-r"),
        weak_terms=("ira", "annuity", "pension", "distribution", "taxable amount", "box 2a"),
        negative_terms=("w-2", "1099-int", "1099-div"),
    ),
    DocModel(
        name="SSA-1099",
        strong_terms=("ssa-1099", "rrb-1099"),
        weak_terms=("social security benefit statement", "benefits paid", "box 5"),
        negative_terms=("w-2", "1099-int", "1099-div"),
    ),
    DocModel(
        name="1099-B",
        strong_terms=("form 1099-b", "1099-b", "1099 composite", "year-end summary"),
        weak_terms=("proceeds", "cost basis", "gain or loss", "capital gain", "capital loss"),
        negative_terms=("w-2", "1098-e", "ssa-1099"),
    ),
    DocModel(
        name="1099-NEC",
        strong_terms=("form 1099-nec", "1099-nec"),
        weak_terms=("nonemployee compensation", "box 1"),
        negative_terms=("w-2", "1099-int", "1099-div"),
    ),
    DocModel(
        name="1098-E",
        strong_terms=("form 1098-e", "1098-e"),
        weak_terms=("student loan interest", "box 1", "received by lender"),
        negative_terms=("w-2", "1099"),
    ),
    DocModel(
        name="Medical/Receipt",
        strong_terms=("medical receipt", "doctor", "physician", "hospital", "pharmacy", "clinic", "dental", "copay"),
        weak_terms=("invoice", "receipt", "amount due", "total", "patient", "insurance", "prescription", "bill"),
        negative_terms=("driver license", "w-2", "1099", "ssa-1099"),
        min_score=0.52,
    ),
)


MONEY_RE = re.compile(r"[-(]?\$?\s*([0-9][0-9,]*(?:\.[0-9]{2})?)\)?")
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]{2,}")
STOPWORDS = {
    "the",
    "and",
    "for",
    "from",
    "with",
    "your",
    "this",
    "that",
    "page",
    "form",
    "name",
    "address",
    "tax",
    "statement",
}


def _normalize(s: str) -> str:
    return s.lower().strip()


def _contains(text: str, term: str) -> bool:
    return term in text


def _parse_money_token(token: str) -> float:
    cleaned = token.replace(",", "").replace("$", "").strip()
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _extract_amounts_from_line(line: str) -> list[float]:
    values: list[float] = []
    for m in MONEY_RE.finditer(line):
        raw = m.group(0)
        amt = _parse_money_token(m.group(1))
        if amt <= 0:
            continue
        if raw.strip().startswith("-") or raw.strip().startswith("("):
            amt = -amt
        values.append(amt)
    return values


def _first_amount_near(lines: list[str], anchors: tuple[str, ...]) -> float:
    for i, line in enumerate(lines):
        ln = _normalize(line)
        if any(a in ln for a in anchors):
            vals = _extract_amounts_from_line(line)
            if vals:
                return vals[-1]
            if i + 1 < len(lines):
                vals = _extract_amounts_from_line(lines[i + 1])
                if vals:
                    return vals[-1]
    return 0.0


def _max_total_like_amount(lines: list[str]) -> float:
    total_markers = ("total", "amount due", "balance", "patient responsibility", "you owe", "paid")
    candidates: list[float] = []
    for line in lines:
        ln = _normalize(line)
        if any(k in ln for k in total_markers):
            candidates.extend([v for v in _extract_amounts_from_line(line) if v > 0])
    if not candidates:
        return 0.0
    return max(candidates)


class DocumentClassifierAgent:
    """Classifies tax-relevant documents with confidence gating."""

    def __init__(self) -> None:
        self.feedback_path = Path(settings.data_dir) / "classifier_feedback.json"
        self.feedback_path.parent.mkdir(parents=True, exist_ok=True)
        self.feedback = self._load_feedback()

    def _load_feedback(self) -> dict[str, Any]:
        if self.feedback_path.exists():
            try:
                data = json.loads(self.feedback_path.read_text(encoding="utf-8"))
                data.setdefault("class_bias", {})
                data.setdefault("token_class_weights", {})
                data.setdefault("feedback_count", 0)
                data.setdefault("confusion_matrix", {})
                data.setdefault("class_feedback_counts", {})
                return data
            except Exception:
                pass
        return {
            "class_bias": {},
            "token_class_weights": {},
            "feedback_count": 0,
            "confusion_matrix": {},
            "class_feedback_counts": {},
        }

    def _save_feedback(self) -> None:
        self.feedback_path.write_text(json.dumps(self.feedback, indent=2), encoding="utf-8")

    def _tokenize(self, text: str, filename: str) -> list[str]:
        tokens = [t.lower() for t in TOKEN_RE.findall(f"{filename} {text[:1200]}")]
        return [t for t in tokens if t not in STOPWORDS]

    def _feedback_boost(self, class_name: str, tokens: list[str]) -> float:
        class_bias = float(self.feedback.get("class_bias", {}).get(class_name, 0.0))
        token_weights = self.feedback.get("token_class_weights", {})
        token_score = 0.0
        for t in tokens[:80]:
            token_score += float(token_weights.get(t, {}).get(class_name, 0.0))
        token_score = max(-0.15, min(0.25, token_score))
        return max(-0.25, min(0.35, class_bias + token_score))

    def _score_model(self, model: DocModel, text: str, filename: str, tokens: list[str]) -> float:
        t = _normalize(text)
        fn = _normalize(filename)

        strong_text_hits = sum(1 for term in model.strong_terms if _contains(t, term))
        weak_text_hits = sum(1 for term in model.weak_terms if _contains(t, term))
        strong_fn_hits = sum(1 for term in model.strong_terms if _contains(fn, term.replace("form ", "")))
        weak_fn_hits = sum(1 for term in model.weak_terms if _contains(fn, term))
        neg_hits = sum(1 for term in model.negative_terms if _contains(t, term) or _contains(fn, term))

        score = 0.0
        score += min(0.7, 0.32 * strong_text_hits)
        score += min(0.2, 0.08 * weak_text_hits)
        score += min(0.45, 0.25 * strong_fn_hits)
        score += min(0.12, 0.06 * weak_fn_hits)
        score -= min(0.45, 0.15 * neg_hits)
        score += self._feedback_boost(model.name, tokens)

        # Medical receipts need both medical context and receipt context.
        if model.name == "Medical/Receipt":
            medical_hits = sum(1 for term in ("medical", "doctor", "hospital", "pharmacy", "clinic", "dental") if term in t)
            receipt_hits = sum(1 for term in ("receipt", "invoice", "amount due", "total", "patient") if term in t)
            if medical_hits == 0 or receipt_hits == 0:
                score -= 0.25

        return max(0.0, min(1.0, score))

    def record_feedback(
        self,
        *,
        predicted_doc_type: str,
        corrected_doc_type: str,
        filename: str,
        raw_snippet: str = "",
        accepted: bool = True,
    ) -> int:
        """Update learned score biases/weights from user feedback."""
        predicted = predicted_doc_type.strip() or "Unknown"
        corrected = corrected_doc_type.strip() or "Unknown"

        class_bias: dict[str, float] = self.feedback.setdefault("class_bias", {})
        token_weights: dict[str, dict[str, float]] = self.feedback.setdefault("token_class_weights", {})
        confusion: dict[str, dict[str, int]] = self.feedback.setdefault("confusion_matrix", {})
        class_counts: dict[str, int] = self.feedback.setdefault("class_feedback_counts", {})
        tokens = self._tokenize(raw_snippet, filename)[:100]

        def bump_bias(label: str, delta: float) -> None:
            class_bias[label] = max(-0.4, min(0.6, float(class_bias.get(label, 0.0)) + delta))

        def bump_token(token: str, label: str, delta: float) -> None:
            bucket = token_weights.setdefault(token, {})
            bucket[label] = max(-0.2, min(0.3, float(bucket.get(label, 0.0)) + delta))

        if accepted and predicted == corrected:
            bump_bias(corrected, 0.02)
            for tok in tokens:
                bump_token(tok, corrected, 0.01)
        else:
            bump_bias(corrected, 0.04)
            if predicted != corrected:
                bump_bias(predicted, -0.03)
            for tok in tokens:
                bump_token(tok, corrected, 0.02)
                if predicted != corrected:
                    bump_token(tok, predicted, -0.01)

        # Track correction patterns/statistics.
        class_counts[corrected] = int(class_counts.get(corrected, 0)) + 1
        row = confusion.setdefault(predicted, {})
        row[corrected] = int(row.get(corrected, 0)) + 1

        self.feedback["feedback_count"] = int(self.feedback.get("feedback_count", 0)) + 1
        self._save_feedback()
        return int(self.feedback["feedback_count"])

    def get_feedback_stats(self) -> dict[str, Any]:
        """Return compact feedback stats for UI dashboards."""
        confusion = self.feedback.get("confusion_matrix", {})
        class_counts = self.feedback.get("class_feedback_counts", {})
        class_bias = self.feedback.get("class_bias", {})

        confusion_rows: list[dict[str, Any]] = []
        for predicted, targets in confusion.items():
            for corrected, count in (targets or {}).items():
                confusion_rows.append(
                    {
                        "predicted": predicted,
                        "corrected": corrected,
                        "count": int(count),
                    }
                )

        top_confusions = sorted(
            [r for r in confusion_rows if r["predicted"] != r["corrected"]],
            key=lambda r: r["count"],
            reverse=True,
        )[:8]

        top_classes = sorted(
            [{"doc_type": k, "count": int(v)} for k, v in class_counts.items()],
            key=lambda r: r["count"],
            reverse=True,
        )[:8]

        return {
            "feedback_count": int(self.feedback.get("feedback_count", 0)),
            "top_confusions": top_confusions,
            "top_classes": top_classes,
            "class_bias": {k: round(float(v), 3) for k, v in class_bias.items()},
        }

    def _extract_fields(self, doc_type: str, text: str, lines: list[str]) -> dict[str, float]:
        fields: dict[str, float] = {}

        if doc_type == "W-2":
            wages = _first_amount_near(lines, ("wages, tips, other compensation", "box 1"))
            fed = _first_amount_near(lines, ("federal income tax withheld", "box 2"))
            if wages > 0:
                fields["wages"] = wages
            if fed > 0:
                fields["fed_tax_withheld"] = fed
            return fields

        if doc_type == "1099-INT":
            amt = _first_amount_near(lines, ("interest income", "box 1"))
            if amt > 0:
                fields["taxable_interest"] = amt
            return fields

        if doc_type == "1099-DIV":
            ordinary = _first_amount_near(lines, ("ordinary dividends", "box 1a", "1a"))
            qualified = _first_amount_near(lines, ("qualified dividends", "box 1b", "1b"))
            if ordinary > 0:
                fields["ordinary_dividends"] = ordinary
            if qualified > 0:
                fields["qualified_dividends"] = qualified
            return fields

        if doc_type == "1099-R":
            taxable = _first_amount_near(lines, ("taxable amount", "box 2a", "2a"))
            if taxable > 0:
                if "ira" in text:
                    fields["taxable_ira"] = taxable
                else:
                    fields["taxable_pension"] = taxable
            return fields

        if doc_type == "SSA-1099":
            amt = _first_amount_near(lines, ("benefits paid", "net benefits", "box 5"))
            if amt > 0:
                fields["taxable_social_security"] = amt
            return fields

        if doc_type == "1099-B":
            # Prefer gain/loss lines; fall back to proceeds.
            gain = _first_amount_near(lines, ("gain", "loss", "net gain", "net loss", "capital gain", "capital loss"))
            if gain == 0:
                gain = _first_amount_near(lines, ("proceeds", "cost basis"))
            if abs(gain) > 0:
                fields["capital_gain_loss"] = gain
            return fields

        if doc_type == "1099-NEC":
            amt = _first_amount_near(lines, ("nonemployee compensation", "box 1"))
            if amt > 0:
                fields["sch_c_income"] = amt
            return fields

        if doc_type == "1098-E":
            amt = _first_amount_near(lines, ("student loan interest", "box 1", "received by lender"))
            if amt > 0:
                fields["student_loan_interest"] = amt
            return fields

        if doc_type == "Medical/Receipt":
            total = _max_total_like_amount(lines)
            # Guardrails to avoid tiny OCR artifacts (e.g. "$1" from IDs)
            if total >= 20:
                fields["medical_expenses"] = total
            return fields

        return fields

    def classify_and_extract(self, filename: str, markdown: str) -> ClassifiedDocument:
        """Classify document type and extract mapped tax fields."""
        if not markdown or not markdown.strip():
            return ClassifiedDocument(filename=filename, doc_type="Unknown", confidence=0.0)

        text = markdown.lower()
        lines = [line.strip() for line in markdown.splitlines() if line.strip()]

        best_name = "Unknown"
        best_score = 0.0
        scores: dict[str, float] = {}
        tokens = self._tokenize(markdown, filename)

        for model in DOC_MODELS:
            score = self._score_model(model, markdown, filename, tokens)
            scores[model.name] = round(score, 3)
            if score > best_score:
                best_name = model.name
                best_score = score

        model = next((m for m in DOC_MODELS if m.name == best_name), None)
        if model is None or best_score < model.min_score:
            best_name = "Unknown"
            extracted: dict[str, float] = {}
            best_score = min(best_score, 0.39)
        else:
            extracted = self._extract_fields(best_name, text, lines)
            # Slight confidence boost when extraction succeeds.
            if extracted:
                best_score = min(1.0, best_score + 0.1)

        # IDs or unknown docs should not produce tax fields.
        if best_name in ("Government ID", "Unknown"):
            extracted = {}

        snippet = markdown[:500] if len(markdown) > 500 else markdown
        return ClassifiedDocument(
            filename=filename,
            doc_type=best_name,
            confidence=round(best_score, 2),
            extracted_fields=extracted,
            raw_snippet=snippet,
            score_breakdown=scores,
        )
