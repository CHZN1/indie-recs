"""Experimental local content scoring; not enabled in the recommendation API."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS

# Leave negation tokens in the vocabulary. Bag of words still cannot interpret
# their scope: "not funny" may match "funny" and needs separate evaluation.
STOP_WORDS = sorted(ENGLISH_STOP_WORDS - {'no', 'not', 'never', 'nor'})


def clean_review(text: str) -> str:
    return html.unescape(re.sub(r'<[^>]*>', ' ', text or ''))


@dataclass(frozen=True)
class ReviewExample:
    item_id: int
    rating: float
    text: str


class ReviewTextModel:
    """TF-IDF unigrams/bigrams, signed rating weights, cosine similarity.

    The vocabulary/IDF is fit only on public movie metadata. User reviews are
    transformed, never fit, so held-out reviews cannot affect the vocabulary.
    Titles are omitted from metadata to reduce simple name matching.
    """

    def __init__(self, documents: dict[int, str], max_features: int | None = 20000):
        self.item_ids = list(documents)
        self.positions = {item: i for i, item in enumerate(self.item_ids)}
        self.vectorizer = TfidfVectorizer(
            lowercase=True, strip_accents='unicode', stop_words=STOP_WORDS,
            ngram_range=(1, 2), sublinear_tf=True, max_features=max_features,
        )
        try:
            self.matrix = self.vectorizer.fit_transform([documents[i] for i in self.item_ids])
        except ValueError as exc:
            raise ValueError('Movie metadata needs at least one usable word.') from exc

    def profile(self, examples: list[ReviewExample], source: str = 'reviews') -> np.ndarray:
        if source not in {'reviews', 'metadata'}:
            raise ValueError('Profile source must be reviews or metadata.')
        vector = np.zeros(self.matrix.shape[1], dtype=float)
        for row in examples:
            weight = (row.rating - 5.0) / 5.0
            if source == 'reviews':
                encoded = self.vectorizer.transform([clean_review(row.text)])
            elif row.item_id in self.positions:
                encoded = self.matrix[self.positions[row.item_id]]
            else:
                continue
            vector += weight * encoded.toarray().ravel()
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector

    def scores(self, examples: list[ReviewExample], source: str = 'reviews') -> dict[int, float]:
        scores = np.asarray(self.matrix @ self.profile(examples, source)).ravel()
        return {item: float(score) for item, score in zip(self.item_ids, scores)}

    def explain(self, examples: list[ReviewExample], item_id: int, limit: int = 8) -> list[dict]:
        profile = self.profile(examples)
        item = self.matrix[self.positions[item_id]].toarray().ravel()
        contributions = profile * item
        terms = self.vectorizer.get_feature_names_out()
        indices = np.argsort(-contributions, kind='stable')[:limit]
        return [{'term': str(terms[i]), 'contribution': round(float(contributions[i]), 5)}
                for i in indices if contributions[i] > 0]

    def review_coverage(self, text: str) -> dict:
        terms = set(self.vectorizer.build_analyzer()(clean_review(text)))
        matched = sorted(terms & self.vectorizer.vocabulary_.keys())
        return {'terms': len(terms), 'matched_terms': len(matched),
                'fraction': round(len(matched) / len(terms), 4) if terms else 0,
                'matched_examples': matched[:20]}


def percentile_scores(values: dict[int, float]) -> dict[int, float]:
    """Ascending average-tie percentiles for blending incompatible score scales."""
    import pandas as pd
    if len(values) < 2:
        return {item: 0.5 for item in values}
    ranks = pd.Series(values).rank(method='average')
    return {int(item): float((rank - 1) / (len(values) - 1)) for item, rank in ranks.items()}


def blend_scores(cf: dict[int, float], text: dict[int, float], weight: float) -> dict[int, float]:
    if not 0 <= weight <= 1 or cf.keys() != text.keys():
        raise ValueError('Blend needs equal candidates and a weight between zero and one.')
    left, right = percentile_scores(cf), percentile_scores(text)
    # Zero review signal must preserve CF ordering, including tiny-score ties.
    if not any(abs(score) > 1e-12 for score in text.values()):
        return left
    return {item: (1-weight)*left[item] + weight*right[item] for item in left}


def ranking_metrics(scores: dict[int, float], target: int, k: int = 10) -> dict:
    """Expected metrics under random ordering of score ties, not item-ID luck."""
    value = scores[target]
    above = sum(v > value + 1e-12 for v in scores.values())
    tied = sum(abs(v-value) <= 1e-12 for v in scores.values())
    ranks = np.arange(above+1, above+tied+1, dtype=float)
    return {'rank': float(ranks.mean()), 'hit_at_10': float(np.mean(ranks <= k)),
            'mrr': float(np.mean(1/ranks)),
            'ndcg_at_10': float(np.mean(np.where(ranks <= k, 1/np.log2(ranks+1), 0)))}
