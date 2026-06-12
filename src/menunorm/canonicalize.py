"""Similarity-based canonicalization of normalized product names.

The original workflow mapped variants to standard labels by hand-editing one
regex at a time. This module replaces that with a single principled matcher:

1. Exact match against the canonical lexicon (after space removal) - free.
2. Character n-gram TF-IDF + cosine similarity against the lexicon, with an
   abstention threshold: names below the threshold are marked ``UNMATCHED``
   instead of being force-assigned, and are handed to the discovery step
   (:mod:`menunorm.cluster`) to propose *new* canonical labels.

Character n-grams (rather than word tokens) make the matcher robust to the
dominant noise modes in this domain: spacing variants (아메리 카노), glued
options (아메리카노세트), and partial spelling drift.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

UNMATCHED = "UNMATCHED"


class Canonicalizer:
    """Match noisy names to a fixed canonical label set.

    Args:
        labels: Canonical label inventory.
        ngram_range: Character n-gram range for the TF-IDF index.
        threshold: Cosine-similarity abstention threshold; matches scoring
            below it are reported as ``UNMATCHED``.
    """

    def __init__(
        self,
        labels: list[str],
        ngram_range: tuple[int, int] = (2, 4),
        threshold: float = 0.45,
    ) -> None:
        if not labels:
            raise ValueError("canonical label set is empty")
        self.labels = list(dict.fromkeys(labels))  # dedupe, keep order
        self.threshold = threshold
        self._vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=ngram_range)
        self._index = self._vectorizer.fit_transform(self.labels)
        self._exact = {lbl.replace(" ", ""): lbl for lbl in self.labels}

    # ------------------------------------------------------------------ core
    def score(self, names: list[str]) -> pd.DataFrame:
        """Score each name against the lexicon without applying the threshold.

        Both the spaced and space-collapsed forms of each name are scored and
        the better one is kept, which handles spacing-noise symmetrically.

        Args:
            names: Normalized (post-rules, post-stopword) name strings.

        Returns:
            DataFrame with columns ``name``, ``best_label``, ``score``,
            ``method`` (``exact`` | ``tfidf`` | ``empty``), one row per
            *unique* input name.
        """
        unique = list(dict.fromkeys(names))
        rows: list[dict[str, object]] = []
        to_score: list[str] = []

        for name in unique:
            collapsed = name.replace(" ", "")
            if not collapsed:
                rows.append(
                    {"name": name, "best_label": UNMATCHED, "score": 0.0, "method": "empty"}
                )
            elif collapsed in self._exact:
                rows.append(
                    {
                        "name": name,
                        "best_label": self._exact[collapsed],
                        "score": 1.0,
                        "method": "exact",
                    }
                )
            else:
                to_score.append(name)

        if to_score:
            spaced = self._vectorizer.transform(to_score)
            collapsed = self._vectorizer.transform([n.replace(" ", "") for n in to_score])
            sims = np.maximum(
                linear_kernel(spaced, self._index), linear_kernel(collapsed, self._index)
            )
            best_idx = sims.argmax(axis=1)
            best_score = sims[np.arange(len(to_score)), best_idx]
            for name, idx, sc in zip(to_score, best_idx, best_score):
                rows.append(
                    {
                        "name": name,
                        "best_label": self.labels[int(idx)],
                        "score": float(sc),
                        "method": "tfidf",
                    }
                )
        return pd.DataFrame(rows)

    def match(self, names: list[str], threshold: float | None = None) -> pd.DataFrame:
        """Score names and apply the abstention threshold.

        Returns:
            DataFrame as in :meth:`score` plus a ``pred_label`` column that is
            ``best_label`` where ``score >= threshold`` and ``UNMATCHED``
            otherwise.
        """
        thr = self.threshold if threshold is None else threshold
        scored = self.score(names)
        scored["pred_label"] = np.where(
            (scored["score"] >= thr) & (scored["method"] != "empty"),
            scored["best_label"],
            UNMATCHED,
        )
        return scored
