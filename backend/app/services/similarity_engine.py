import math
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from app.core.config import settings
from app.models.entities import MatchTier

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
_STOPWORDS = frozenset(
    "a an the of to in on for and or is are was were be been being with by at from as that this these those "
    "it its into than then there their them they which what who whom whose how why when where your you i we "
    "our us do does did can could should would will shall may might must also any all each both such".split()
)


def tokenize(text: str) -> List[str]:
    """Lower-cased word tokens without stopwords. Numbers are kept (numerical value swaps matter)."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


class LexicalIndex:
    """BM25 over a corpus, with scores normalised by the query's self-score so they lie in [0, 1].

    Raw BM25 is unbounded; dividing by the best score in the candidate set (the previous approach) made the
    top candidate score 1.0 even when it was unrelated. Normalising by the score a document identical to the
    query would receive gives ~1.0 for verbatim repeats and ~0 for unrelated text regardless of pool size.
    """

    def __init__(self, documents: Iterable[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        tokenized = [tokenize(d) for d in documents]
        self.n_docs = len(tokenized)
        self.avg_len = (sum(len(t) for t in tokenized) / self.n_docs) if self.n_docs else 0.0
        self.doc_freq: Counter = Counter()
        for toks in tokenized:
            self.doc_freq.update(set(toks))

    def idf(self, term: str) -> float:
        df = self.doc_freq.get(term, 0)
        # Lucene-style IDF: always positive, unlike Okapi's which goes negative for common terms.
        return math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))

    def _score(self, query_terms: Counter, doc_tokens: List[str]) -> float:
        if not doc_tokens:
            return 0.0
        tf = Counter(doc_tokens)
        avg_len = self.avg_len or len(doc_tokens)
        norm = self.k1 * (1 - self.b + self.b * len(doc_tokens) / avg_len)
        score = 0.0
        for term in query_terms:
            f = tf.get(term, 0)
            if f:
                score += self.idf(term) * (f * (self.k1 + 1)) / (f + norm)
        return score

    def similarity(self, query: str, document: str) -> float:
        q_tokens = tokenize(query)
        if not q_tokens:
            return 0.0
        q_terms = Counter(q_tokens)
        self_score = self._score(q_terms, q_tokens)
        if self_score <= 0:
            return 0.0
        return min(1.0, self._score(q_terms, tokenize(document)) / self_score)


class SimilarityResult:
    def __init__(
        self,
        historical_question_id: str,
        semantic_score: float,
        lexical_score: float,
        composite_score: float,
        match_tier: MatchTier
    ):
        self.historical_question_id = historical_question_id
        self.semantic_score = round(semantic_score, 4)
        self.lexical_score = round(lexical_score, 4)
        self.composite_score = round(composite_score, 4)
        self.match_tier = match_tier


class HybridSimilarityEngine:
    """Deterministic hybrid similarity combining vector cosine similarity and normalised BM25."""

    def __init__(
        self,
        exact_threshold: float = settings.EXACT_MATCH_THRESHOLD,
        paraphrase_threshold: float = settings.PARAPHRASE_MATCH_THRESHOLD,
        conceptual_threshold: float = settings.CONCEPTUAL_MATCH_THRESHOLD,
        alpha: float = settings.SEMANTIC_WEIGHT,
    ):
        self.exact_threshold = exact_threshold
        self.paraphrase_threshold = paraphrase_threshold
        self.conceptual_threshold = conceptual_threshold
        self.alpha = alpha

    @staticmethod
    def compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        v1 = np.asarray(vec1, dtype=np.float32)
        v2 = np.asarray(vec2, dtype=np.float32)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.clip(np.dot(v1, v2) / (norm1 * norm2), -1.0, 1.0))

    def classify(self, composite_score: float) -> Optional[MatchTier]:
        if composite_score >= self.exact_threshold:
            return MatchTier.EXACT
        if composite_score >= self.paraphrase_threshold:
            return MatchTier.PARAPHRASED
        if composite_score >= self.conceptual_threshold:
            return MatchTier.CONCEPTUAL
        return None

    def find_matches_for_question(
        self,
        draft_text: str,
        draft_embedding: List[float],
        historical_questions: List[Dict[str, Any]],
        lexical_index: Optional[LexicalIndex] = None,
    ) -> List[SimilarityResult]:
        """Score `historical_questions` (dicts with id, clean_text, embedding) against one draft question.

        `lexical_index` supplies corpus statistics (IDF); by default it is built from the candidates.
        """
        if not historical_questions:
            return []
        if lexical_index is None:
            lexical_index = LexicalIndex(q["clean_text"] for q in historical_questions)

        results = []
        for h_q in historical_questions:
            h_vec = h_q.get("embedding")
            sem_score = max(0.0, self.compute_cosine_similarity(draft_embedding, h_vec)) if h_vec is not None else 0.0
            lex_score = lexical_index.similarity(draft_text, h_q["clean_text"])
            comp_score = (self.alpha * sem_score) + ((1 - self.alpha) * lex_score)
            tier = self.classify(comp_score)
            if tier:
                results.append(
                    SimilarityResult(
                        historical_question_id=str(h_q["id"]),
                        semantic_score=sem_score,
                        lexical_score=lex_score,
                        composite_score=comp_score,
                        match_tier=tier,
                    )
                )

        results.sort(key=lambda r: r.composite_score, reverse=True)
        return results
