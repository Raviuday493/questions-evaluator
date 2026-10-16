"""Deterministic paper analytics: originality scoring, unit coverage, Bloom's/format distributions,
5-year topic saturation, conceptual gaps and next-paper recommendations.

Everything here is pure computation over plain dataclasses so it can be unit-tested without a database.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set

from app.models.entities import BloomsLevel, MatchTier, QuestionType, RecommendationCategory

TIER_WEIGHTS: Dict[MatchTier, float] = {
    MatchTier.EXACT: 1.0,
    MatchTier.PARAPHRASED: 0.7,
    MatchTier.CONCEPTUAL: 0.4,
}
OVERREPRESENTED_PERCENT = 35.0
UNDERREPRESENTED_PERCENT = 10.0
SATURATION_WINDOW_YEARS = 5
TERM_ORDER = {"fall": 0, "spring": 1, "summer": 2}
HIGHER_ORDER = (BloomsLevel.APPLY, BloomsLevel.ANALYZE, BloomsLevel.EVALUATE, BloomsLevel.CREATE)


@dataclass
class UnitInfo:
    id: str
    unit_number: int
    title: str
    target_percent: float


@dataclass
class MatchInfo:
    tier: MatchTier
    composite_score: float
    source_label: str  # e.g. "Fall 2021 Final Examination"
    source_question_number: str


@dataclass
class QuestionInfo:
    id: str
    number: str
    text: str
    marks: int
    parent_id: Optional[str] = None
    unit_id: Optional[str] = None
    blooms: Optional[BloomsLevel] = None
    qtype: Optional[QuestionType] = None
    best_match: Optional[MatchInfo] = None


@dataclass
class HistoricalCycle:
    academic_year: str
    term: str
    unit_ids: Set[str] = field(default_factory=set)


@dataclass
class RecommendationDraft:
    category: RecommendationCategory
    action_text: str
    rationale: str
    severity: float
    target_question_id: Optional[str] = None


def academic_year_start(academic_year: str) -> Optional[int]:
    m = re.match(r"^\s*(\d{4})", academic_year or "")
    return int(m.group(1)) if m else None


def cycle_sort_key(academic_year: str, term: str) -> tuple:
    return (academic_year_start(academic_year) or 0, TERM_ORDER.get((term or "").lower(), 3))


def term_label(academic_year: str, term: str) -> str:
    """'2021-2022' + 'Spring' -> 'Spring 2022' (Fall falls in the first calendar year)."""
    start = academic_year_start(academic_year)
    if start is None:
        return f"{term} {academic_year}".strip()
    year = start if (term or "").lower() == "fall" else start + 1
    return f"{term} {year}"


class PaperAnalytics:
    def __init__(self, questions: Sequence[QuestionInfo], units: Sequence[UnitInfo], history: Sequence[HistoricalCycle]):
        self.questions = list(questions)
        self.units = sorted(units, key=lambda u: u.unit_number)
        self.history = list(history)
        self._by_id = {q.id: q for q in self.questions}
        children: Dict[str, List[QuestionInfo]] = {}
        for q in self.questions:
            if q.parent_id and q.parent_id in self._by_id:
                children.setdefault(q.parent_id, []).append(q)
        self._children = children
        # Leaves are the scoring units; a parent's marks are distributed to unmarked children.
        self.leaves = [q for q in self.questions if q.id not in children]
        self.weights = self._compute_weights()

    # ------------------------------------------------------------------ weighting
    def _parent(self, q: QuestionInfo) -> Optional[QuestionInfo]:
        return self._by_id.get(q.parent_id) if q.parent_id else None

    def _effective_marks(self, q: QuestionInfo) -> float:
        if q.marks > 0:
            return float(q.marks)
        parent = self._parent(q)
        if parent and parent.marks > 0:
            siblings = self._children.get(parent.id, [])
            if all(s.marks == 0 for s in siblings):
                return parent.marks / len(siblings)
        return 0.0

    def _compute_weights(self) -> Dict[str, float]:
        marks = {q.id: self._effective_marks(q) for q in self.leaves}
        total = sum(marks.values())
        if total <= 0:
            n = len(self.leaves)
            return {q.id: 1.0 / n for q in self.leaves} if n else {}
        return {qid: m / total for qid, m in marks.items()}

    def leaf_tier(self, q: QuestionInfo) -> Optional[MatchTier]:
        """A leaf inherits its parent's match: if the stem is recycled, so is the sub-part."""
        candidates = [m.tier for m in (q.best_match, getattr(self._parent(q), "best_match", None)) if m]
        return max(candidates, key=lambda t: TIER_WEIGHTS[t]) if candidates else None

    def leaf_unit(self, q: QuestionInfo) -> Optional[str]:
        parent = self._parent(q)
        return q.unit_id or (parent.unit_id if parent else None)

    # ------------------------------------------------------------------ metrics
    def originality_score(self) -> float:
        """100% - sum(weight_i * QR_i * 100%), floored at 0 (plan.md §4.9)."""
        deduction = sum(
            self.weights[q.id] * TIER_WEIGHTS[tier] for q in self.leaves if (tier := self.leaf_tier(q))
        )
        return round(max(0.0, 100.0 * (1.0 - deduction)), 2)

    def matched_questions(self) -> List[QuestionInfo]:
        return [q for q in self.questions if q.best_match]

    def severity_breakdown(self) -> Dict[str, int]:
        counts = {t.value: 0 for t in MatchTier}
        for q in self.matched_questions():
            counts[q.best_match.tier.value] += 1
        return counts

    def unit_coverage(self) -> Dict:
        per_unit = {u.id: 0.0 for u in self.units}
        counts = {u.id: 0 for u in self.units}
        unassigned = 0.0
        for q in self.leaves:
            uid = self.leaf_unit(q)
            if uid in per_unit:
                per_unit[uid] += self.weights[q.id]
                counts[uid] += 1
            else:
                unassigned += self.weights[q.id]
        units = []
        for u in self.units:
            actual = round(per_unit[u.id] * 100, 1)
            status = "BALANCED"
            if actual > OVERREPRESENTED_PERCENT:
                status = "OVER"
            elif actual < UNDERREPRESENTED_PERCENT:
                status = "UNDER"
            units.append({
                "unit_id": u.id,
                "unit_number": u.unit_number,
                "title": u.title,
                "target_percent": round(u.target_percent, 1),
                "actual_percent": actual,
                "question_count": counts[u.id],
                "status": status,
            })
        return {"units": units, "unassigned_percent": round(unassigned * 100, 1)}

    def _distribution(self, values: List[str], keys: List[str]) -> Dict:
        total = len(values)
        counts = {k: values.count(k) for k in keys}
        return {
            "total": total,
            "counts": counts,
            "percentages": {k: (round(100 * c / total, 1) if total else 0.0) for k, c in counts.items()},
        }

    def blooms_distribution(self) -> Dict:
        values = [q.blooms.value for q in self.leaves if q.blooms]
        dist = self._distribution(values, [b.value for b in BloomsLevel])
        higher = sum(dist["counts"][b.value] for b in HIGHER_ORDER)
        dist["higher_order_percent"] = round(100 * higher / len(values), 1) if values else 0.0
        return dist

    def question_types(self) -> Dict:
        values = [q.qtype.value for q in self.leaves if q.qtype]
        return self._distribution(values, [t.value for t in QuestionType])

    def _cycles_desc(self) -> List[HistoricalCycle]:
        merged: Dict[tuple, HistoricalCycle] = {}
        for c in self.history:
            key = (c.academic_year, c.term)
            if key not in merged:
                merged[key] = HistoricalCycle(c.academic_year, c.term, set())
            merged[key].unit_ids |= c.unit_ids
        return sorted(merged.values(), key=lambda c: cycle_sort_key(c.academic_year, c.term), reverse=True)

    def overused_topics(self, current_academic_year: str) -> List[Dict]:
        """How often each unit was examined in historical cycles of the last 5 academic years."""
        current_start = academic_year_start(current_academic_year)
        cycles = [
            c for c in self._cycles_desc()
            if current_start is None
            or (academic_year_start(c.academic_year) or 0) > current_start - SATURATION_WINDOW_YEARS - 1
        ][:SATURATION_WINDOW_YEARS]
        if not cycles:
            return []
        coverage = self.unit_coverage()["units"]
        in_draft = {u["unit_id"]: u["actual_percent"] for u in coverage}
        results = []
        for u in self.units:
            tested = sum(1 for c in cycles if u.id in c.unit_ids)
            results.append({
                "unit_id": u.id,
                "unit_number": u.unit_number,
                "title": u.title,
                "cycles_tested": tested,
                "cycles_total": len(cycles),
                "saturated": len(cycles) >= 3 and tested / len(cycles) >= 0.8,
                "draft_percent": in_draft.get(u.id, 0.0),
            })
        return results

    def conceptual_gaps(self) -> List[Dict]:
        cycles = self._cycles_desc()
        gaps = []
        for u in self.unit_coverage()["units"]:
            if u["status"] != "UNDER":
                continue
            last = next((c for c in cycles if u["unit_id"] in c.unit_ids), None)
            gaps.append({
                **u,
                "last_covered": term_label(last.academic_year, last.term) if last else None,
                "_last_key": cycle_sort_key(last.academic_year, last.term) if last else (0, 0),
            })
        # Most neglected first: never examined, then least recently examined, then largest shortfall.
        gaps.sort(key=lambda g: (g["_last_key"], -(g["target_percent"] - g["actual_percent"])))
        for g in gaps:
            del g["_last_key"]
        return gaps

    # ------------------------------------------------------------------ recommendations
    def recommendations(self, current_academic_year: str, limit: int = 5) -> List[RecommendationDraft]:
        recs: List[RecommendationDraft] = []
        gaps = self.conceptual_gaps()
        blooms = self.blooms_distribution()
        level_hint = " at Apply level or higher" if blooms["total"] and blooms["higher_order_percent"] < 40 else ""

        repeated = sorted(
            (q for q in self.questions if q.best_match and q.best_match.tier in (MatchTier.EXACT, MatchTier.PARAPHRASED)),
            key=lambda q: q.best_match.composite_score,
            reverse=True,
        )
        for i, q in enumerate(repeated[:3]):
            m = q.best_match
            # Spread replacements across the neglected units instead of pointing all of them at one.
            gap = gaps[i % len(gaps)] if gaps else None
            gap_hint = f" from Unit {gap['unit_number']} ({gap['title']})" if gap else ""
            recs.append(RecommendationDraft(
                category=RecommendationCategory.REPETITION_SWAP,
                action_text=f"Replace Q{q.number} with a new question{gap_hint}{level_hint}.",
                rationale=(
                    f"Q{q.number} is a {round(m.composite_score * 100)}% {m.tier.value.lower()} match with "
                    f"Q{m.source_question_number} of the {m.source_label} paper."
                ),
                severity=1.0 + m.composite_score,
                target_question_id=q.id,
            ))

        conceptual = [q for q in self.questions if q.best_match and q.best_match.tier == MatchTier.CONCEPTUAL]
        if conceptual:
            numbers = ", ".join(f"Q{q.number}" for q in conceptual[:4])
            recs.append(RecommendationDraft(
                category=RecommendationCategory.REPETITION_SWAP,
                action_text=f"Rework {numbers} to test the underlying concepts from a fresh angle.",
                rationale=f"{len(conceptual)} question(s) share core concepts with past papers (conceptual matches).",
                severity=0.5,
            ))

        for u in self.unit_coverage()["units"]:
            if u["status"] == "OVER":
                recs.append(RecommendationDraft(
                    category=RecommendationCategory.UNIT_REBALANCE,
                    action_text=f"Reduce the weight of Unit {u['unit_number']} ({u['title']}) towards its {u['target_percent']}% syllabus target.",
                    rationale=f"Unit {u['unit_number']} carries {u['actual_percent']}% of the marks (over the {OVERREPRESENTED_PERCENT:.0f}% limit).",
                    severity=0.8 + (u["actual_percent"] - OVERREPRESENTED_PERCENT) / 100,
                ))
        for g in gaps[:2]:
            last = f" Last covered: {g['last_covered']}." if g["last_covered"] else " Not examined in the archive."
            recs.append(RecommendationDraft(
                category=RecommendationCategory.UNIT_REBALANCE,
                action_text=f"Add a question from Unit {g['unit_number']} ({g['title']}).",
                rationale=f"Unit {g['unit_number']} has {g['actual_percent']}% of marks against a {g['target_percent']}% target.{last}",
                severity=0.7 + max(0.0, g["target_percent"] - g["actual_percent"]) / 100,
            ))

        for t in self.overused_topics(current_academic_year):
            if t["saturated"] and t["draft_percent"] >= UNDERREPRESENTED_PERCENT:
                recs.append(RecommendationDraft(
                    category=RecommendationCategory.UNIT_REBALANCE,
                    action_text=f"Rotate the sub-topics tested from Unit {t['unit_number']} ({t['title']}).",
                    rationale=f"Saturated topic: examined in {t['cycles_tested']} of the last {t['cycles_total']} terms.",
                    severity=0.6,
                ))

        if blooms["total"] and blooms["higher_order_percent"] < 40:
            lower = 100 - blooms["higher_order_percent"]
            recs.append(RecommendationDraft(
                category=RecommendationCategory.BLOOMS_ELEVATION,
                action_text="Add higher-order questions (Apply, Analyze, Evaluate or Create).",
                rationale=f"{lower:.0f}% of questions are Remember/Understand; only {blooms['higher_order_percent']:.0f}% test higher-order thinking.",
                severity=0.65,
            ))

        types = self.question_types()
        if types["total"] >= 4:
            dominant, pct = max(types["percentages"].items(), key=lambda kv: kv[1])
            if pct > 70:
                recs.append(RecommendationDraft(
                    category=RecommendationCategory.FORMAT_DIVERSIFICATION,
                    action_text="Diversify question formats (e.g. add numerical problems, derivations or short answers).",
                    rationale=f"{pct:.0f}% of questions are {dominant.replace('_', ' ').title()}.",
                    severity=0.4,
                ))

        recs.sort(key=lambda r: r.severity, reverse=True)
        return recs[:limit]
