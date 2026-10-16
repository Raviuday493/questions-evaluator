from app.models.entities import BloomsLevel, MatchTier, QuestionType, RecommendationCategory
from app.services.analytics_service import (
    HistoricalCycle,
    MatchInfo,
    PaperAnalytics,
    QuestionInfo,
    UnitInfo,
    term_label,
)

UNITS = [UnitInfo("u1", 1, "Kinematics", 40), UnitInfo("u2", 2, "Dynamics", 30), UnitInfo("u3", 3, "Thermodynamics", 30)]


def _q(qid, marks, unit=None, tier=None, score=0.95, parent=None, blooms=BloomsLevel.APPLY, qtype=QuestionType.NUMERICAL):
    match = MatchInfo(tier, score, "Fall 2021 Final Examination", "2") if tier else None
    return QuestionInfo(qid, qid, f"question {qid}", marks, parent_id=parent, unit_id=unit, blooms=blooms, qtype=qtype, best_match=match)


def test_originality_is_marks_weighted_by_tier():
    qs = [_q("1", 50, "u1", MatchTier.EXACT), _q("2", 30, "u2", MatchTier.CONCEPTUAL), _q("3", 20, "u3")]
    # 100 - (0.5 * 1.0 + 0.3 * 0.4) * 100
    assert PaperAnalytics(qs, UNITS, []).originality_score() == 38.0


def test_originality_without_matches_or_marks():
    qs = [_q("1", 0), _q("2", 0)]
    a = PaperAnalytics(qs, UNITS, [])
    assert a.originality_score() == 100.0
    assert a.weights == {"1": 0.5, "2": 0.5}


def test_sub_questions_inherit_parent_marks_and_match():
    parent = _q("3", 10, "u1", MatchTier.EXACT)
    subs = [_q("3(a)", 0, parent="3"), _q("3(b)", 0, parent="3")]
    other = _q("4", 10, "u3")
    a = PaperAnalytics([parent, *subs, other], UNITS, [])
    assert {q.id for q in a.leaves} == {"3(a)", "3(b)", "4"}
    assert a.weights["3(a)"] == 0.25
    # The recycled stem makes both sub-parts count as repeated: 100 - 50%.
    assert a.originality_score() == 50.0
    # Sub-parts inherit the parent's unit.
    coverage = {u["unit_number"]: u for u in a.unit_coverage()["units"]}
    assert coverage[1]["actual_percent"] == 50.0


def test_unit_coverage_flags_over_and_under_representation():
    qs = [_q("1", 60, "u1"), _q("2", 35, "u2"), _q("3", 5, "u3")]
    coverage = {u["unit_number"]: u["status"] for u in PaperAnalytics(qs, UNITS, []).unit_coverage()["units"]}
    assert coverage == {1: "OVER", 2: "BALANCED", 3: "UNDER"}


def test_gaps_report_last_covered_term_and_saturation():
    history = [
        HistoricalCycle("2021-2022", "Fall", {"u1", "u3"}),
        HistoricalCycle("2022-2023", "Fall", {"u1"}),
        HistoricalCycle("2023-2024", "Spring", {"u1", "u2"}),
        HistoricalCycle("2024-2025", "Fall", {"u1"}),
    ]
    qs = [_q("1", 60, "u1"), _q("2", 40, "u2")]
    a = PaperAnalytics(qs, UNITS, history)
    gaps = a.conceptual_gaps()
    assert [g["unit_number"] for g in gaps] == [3]
    assert gaps[0]["last_covered"] == "Fall 2021"
    topics = {t["unit_number"]: t for t in a.overused_topics("2025-2026")}
    assert topics[1]["cycles_tested"] == 4 and topics[1]["saturated"] is True
    assert topics[3]["saturated"] is False


def test_recommendations_are_prioritised_and_capped():
    history = [HistoricalCycle(f"{y}-{y + 1}", "Fall", {"u1"}) for y in range(2020, 2025)]
    qs = [
        _q("1", 40, "u1", MatchTier.EXACT, 0.97, blooms=BloomsLevel.REMEMBER, qtype=QuestionType.SHORT_ANSWER),
        _q("2", 30, "u1", MatchTier.PARAPHRASED, 0.8, blooms=BloomsLevel.REMEMBER, qtype=QuestionType.SHORT_ANSWER),
        _q("3", 20, "u2", blooms=BloomsLevel.UNDERSTAND, qtype=QuestionType.SHORT_ANSWER),
        _q("4", 10, "u2", blooms=BloomsLevel.REMEMBER, qtype=QuestionType.SHORT_ANSWER),
    ]
    recs = PaperAnalytics(qs, UNITS, history).recommendations("2025-2026")
    assert 3 <= len(recs) <= 5
    assert recs[0].category == RecommendationCategory.REPETITION_SWAP
    assert recs[0].target_question_id == "1"
    assert "Unit 3 (Thermodynamics)" in recs[0].action_text
    categories = {r.category for r in recs}
    assert RecommendationCategory.UNIT_REBALANCE in categories


def test_term_label():
    assert term_label("2021-2022", "Fall") == "Fall 2021"
    assert term_label("2021-2022", "Spring") == "Spring 2022"
