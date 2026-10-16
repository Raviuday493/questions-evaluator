"""Deterministic question classification (question format, Bloom's level, syllabus unit).

research.md reserves Bloom's classification for an LLM agent; this keyword/verb heuristic is the
deterministic first pass and is what runs when no agent is configured.
"""
import re
from typing import Iterable, Optional, Sequence

from app.models.entities import BloomsLevel, QuestionType, SyllabusUnit

# Checked from highest to lowest cognitive level; the first level whose verbs appear wins.
_BLOOMS_VERBS: Sequence[tuple[BloomsLevel, tuple[str, ...]]] = (
    (BloomsLevel.CREATE, ("design", "devise", "formulate", "propose", "construct", "invent", "compose", "develop", "create", "plan")),
    (BloomsLevel.EVALUATE, ("evaluate", "justify", "critique", "assess", "defend", "judge", "argue", "recommend", "appraise", "critically")),
    (BloomsLevel.ANALYZE, ("analyze", "analyse", "compare", "contrast", "differentiate", "distinguish", "examine", "investigate", "categorize", "deduce", "why does", "why do")),
    (BloomsLevel.APPLY, ("calculate", "solve", "compute", "determine", "apply", "find", "derive", "prove", "show that", "implement", "write a program", "estimate", "evaluate the integral")),
    (BloomsLevel.UNDERSTAND, ("explain", "describe", "discuss", "illustrate", "interpret", "summarize", "summarise", "classify", "outline", "what is meant", "give an example")),
    (BloomsLevel.REMEMBER, ("define", "state", "list", "name", "identify", "recall", "what is", "who", "when", "label", "mention", "write down")),
)

_MCQ_PATTERN = re.compile(r"(\(\s*[A-D]\s*\)|\b[A-D][\.\)])\s*\S+.*(\(\s*[B-D]\s*\)|\b[B-D][\.\)])", re.DOTALL)


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def classify_blooms(text: str) -> BloomsLevel:
    lowered = text.lower()
    # "evaluate the integral" is an Apply task, not Evaluate; check that before the generic verb lists.
    if _contains(lowered, "evaluate the integral"):
        return BloomsLevel.APPLY
    for level, verbs in _BLOOMS_VERBS:
        if any(_contains(lowered, v) for v in verbs):
            return level
    return BloomsLevel.UNDERSTAND


def classify_question_type(text: str, marks: int) -> QuestionType:
    lowered = text.lower()
    if _MCQ_PATTERN.search(text) or "choose the correct" in lowered or "multiple choice" in lowered:
        return QuestionType.MCQ
    if any(_contains(lowered, v) for v in ("derive", "prove", "show that", "deduce")):
        return QuestionType.DERIVATION
    if any(_contains(lowered, v) for v in ("calculate", "compute", "solve", "evaluate the integral", "determine the value", "find the value")) or (
        re.search(r"\d", text) and any(_contains(lowered, v) for v in ("find", "determine", "estimate"))
    ):
        return QuestionType.NUMERICAL
    if marks == 1:
        return QuestionType.MCQ
    if marks >= 10 or len(text.split()) > 60:
        return QuestionType.LONG_ESSAY
    return QuestionType.SHORT_ANSWER


def classify_unit(text: str, units: Iterable[SyllabusUnit]) -> Optional[SyllabusUnit]:
    """Pick the syllabus unit whose keywords (and title words) occur most in the question text."""
    lowered = text.lower()
    best: Optional[SyllabusUnit] = None
    best_score = 0.0
    for unit in units:
        score = 0.0
        for keyword in unit.keywords or []:
            kw = str(keyword).strip().lower()
            if kw and _contains(lowered, kw):
                score += 1.0 + 0.5 * (len(kw.split()) - 1)  # multi-word keywords are more specific
        for word in re.findall(r"[a-z]{5,}", unit.title.lower()):
            if _contains(lowered, word):
                score += 0.5
        if score > best_score:
            best, best_score = unit, score
    return best
