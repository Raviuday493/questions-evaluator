from app.models.entities import MatchTier
from app.services.similarity_engine import HybridSimilarityEngine, LexicalIndex


def test_similarity_engine_classification():
    engine = HybridSimilarityEngine(
        exact_threshold=0.90,
        paraphrase_threshold=0.75,
        conceptual_threshold=0.60,
        alpha=0.70,
    )

    draft_text = "Calculate the trajectory of a projectile launched at 45 degrees."
    draft_vec = [1.0] * 768

    historical_qs = [
        {
            "id": "hist_1",
            "clean_text": "Calculate the trajectory of a projectile launched at 45 degrees.",
            "embedding": [1.0] * 768
        },
        {
            "id": "hist_2",
            "clean_text": "Derive the motion equation of a projectile.",
            "embedding": [0.7] + [0.1] * 767
        }
    ]

    matches = engine.find_matches_for_question(draft_text, draft_vec, historical_qs)
    assert len(matches) > 0
    assert matches[0].historical_question_id == "hist_1"
    assert matches[0].match_tier == MatchTier.EXACT
    assert matches[0].composite_score >= 0.90


def test_lexical_score_is_bounded_and_not_inflated_for_unrelated_text():
    index = LexicalIndex(["State the second law of thermodynamics.", "Define entropy."])
    query = "Calculate the acceleration of a 5 kg block."
    # The old max-normalisation gave the best candidate 1.0 even when it was unrelated.
    assert index.similarity(query, "State the second law of thermodynamics.") == 0.0
    assert index.similarity(query, query) == 1.0
    partial = index.similarity(query, "Calculate the velocity of a 5 kg block.")
    assert 0.0 < partial < 1.0


def test_unrelated_questions_are_not_matched():
    engine = HybridSimilarityEngine()
    hist = [{"id": "h", "clean_text": "Explain the Carnot cycle.", "embedding": [0.0, 1.0] + [0.0] * 766}]
    assert engine.find_matches_for_question("Define velocity.", [1.0] + [0.0] * 767, hist) == []


def test_tier_boundaries():
    engine = HybridSimilarityEngine(exact_threshold=0.9, paraphrase_threshold=0.75, conceptual_threshold=0.6)
    assert engine.classify(0.95) == MatchTier.EXACT
    assert engine.classify(0.80) == MatchTier.PARAPHRASED
    assert engine.classify(0.65) == MatchTier.CONCEPTUAL
    assert engine.classify(0.59) is None
