"""Questions for missing brief fields. Not a gate checkpoint."""

from __future__ import annotations

from typing import Any

from .mentions import unresolved_mentions

_ACK_FIELDS = {"audience", "deliverables", "cast_notes", "negative_constraints"}


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
    missing = unresolved_mentions(src)
    if missing:
        listed = ", ".join(f"@{token}" for token in missing)
        questions.append(
            {
                "field": "mentions",
                "question": (
                    f"{listed} has no identity or plate slot. "
                    "Add that name to the cast, or remove the mention. "
                    "A mention does not create an asset."
                ),
            }
        )
    if str(src.get("engine_mode") or "ask").strip().lower() != "approve":
        questions.append(
            {
                "field": "engines",
                "question": (
                    "Approve the still and clip lanes before the crew brief is written. "
                    "Ask stays open until you do. Approving does not call Comfy, and unset lanes stay stub."
                ),
            }
        )
    return questions


def open_questions(answers: dict[str, Any] | None, *, acknowledge_gaps: bool = False) -> list[dict[str, str]]:
    """Content gaps can be acknowledged. Mentions and lane approval cannot."""
    questions = clarify_questions(answers)
    src = answers if isinstance(answers, dict) else {}
    if acknowledge_gaps or src.get("clarify_ack"):
        return [row for row in questions if row["field"] not in _ACK_FIELDS]
    return questions
