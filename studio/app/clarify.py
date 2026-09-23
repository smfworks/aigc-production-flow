"""Questions for missing brief fields. Not a gate checkpoint."""

from __future__ import annotations

from typing import Any


def clarify_questions(answers: dict[str, Any] | None) -> list[dict[str, str]]:
    """Pause before craft lanes when the brief is missing required intake.

    Empty negative constraints are a question until the operator writes ``none``
    or any must-not / claim ban. Checkpoints stay a separate list.
    """
    src = answers if isinstance(answers, dict) else {}
    questions: list[dict[str, str]] = []
    if not str(src.get("audience") or "").strip():
        questions.append(
            {
                "field": "audience",
                "question": "Who is this for? Name the audience before the crew lanes are written.",
            }
        )
    if not str(src.get("deliverables") or "").strip():
        questions.append(
            {
                "field": "deliverables",
                "question": "What are the scoped deliverables? A pilot pack, a vertical cut, a still set — name it.",
            }
        )
    if not str(src.get("cast_notes") or "").strip():
        questions.append(
            {
                "field": "cast_notes",
                "question": "Which faces, products, or places are references? Name them, or write none.",
            }
        )
    must = str(src.get("must_nots") or "").strip()
    bans = str(src.get("claim_bans") or "").strip()
    negative = str(src.get("negative_constraints") or "").strip()
    if not must and not bans and not negative:
        questions.append(
            {
                "field": "negative_constraints",
                "question": "Any negative constraints or must-nots? Write them, or write none.",
            }
        )
    return questions
