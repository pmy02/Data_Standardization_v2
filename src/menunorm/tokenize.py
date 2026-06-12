"""Pluggable tokenization with graceful degradation.

The pipeline prefers MeCab (python-mecab-ko) with a compiled domain user
dictionary; when MeCab is not installed - e.g. on platforms without wheels -
a dependency-free fallback tokenizer keeps the pipeline runnable so that
results remain reproducible everywhere (with a documented quality gap).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Protocol

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[가-힣]+|[a-zA-Z]+")

# POS tags whose surfaces are kept: nouns (NN*, NP, NR), proper nouns, and
# foreign words (SL). Particles, endings, and symbols are dropped.
_KEEP_TAG = re.compile(r"^(N|SL)")


class Tokenizer(Protocol):
    """Minimal tokenizer interface used by the pipeline."""

    name: str

    def analyze(self, text: str) -> list[tuple[str, str]]:
        """Return (surface, POS-tag) pairs for a normalized product name."""
        ...

    def tokenize(self, text: str) -> list[str]:
        """Split a normalized product name into content tokens."""
        ...


class SimpleTokenizer:
    """Whitespace/character-class tokenizer (no external dependencies).

    Every chunk is tagged ``NNG`` so the shared POS filter keeps it.
    """

    name = "simple"

    def analyze(self, text: str) -> list[tuple[str, str]]:
        return [(tok, "NNG") for tok in _TOKEN.findall(text)]

    def tokenize(self, text: str) -> list[str]:
        return _TOKEN.findall(text)


class MecabTokenizer:
    """MeCab-based tokenizer keeping noun-like and foreign-word surfaces.

    Args:
        user_dic_path: Optional compiled ``.dic`` user dictionary.
    """

    name = "mecab"

    def __init__(self, user_dic_path: str | None = None) -> None:
        from mecab import MeCab  # deferred import: optional dependency

        if user_dic_path:
            self._mecab = MeCab(user_dictionary_path=str(user_dic_path))
        else:
            self._mecab = MeCab()

    def analyze(self, text: str) -> list[tuple[str, str]]:
        return self._mecab.pos(text) if text else []

    def tokenize(self, text: str) -> list[str]:
        return [surface for surface, tag in self.analyze(text) if _KEEP_TAG.match(tag)]


def filter_tokens(
    pairs: list[tuple[str, str]], stopwords: set[str], max_span: int = 3
) -> list[str]:
    """Remove stopword spans first, then keep noun-like surfaces.

    Stopword matching runs over the **full** morpheme sequence *before* the
    POS filter, because filtering first can delete inner morphemes and break
    concatenation matching (MeCab tags the 니 in 시그니처 as a copula, so a
    post-filter sequence 시그+처 would never re-join to 시그니처).
    """
    surfaces = [s for s, _ in pairs]
    keep = [True] * len(pairs)
    i = 0
    while i < len(pairs):
        matched = False
        for span in range(min(max_span, len(pairs) - i), 0, -1):
            if "".join(surfaces[i : i + span]) in stopwords:
                for j in range(i, i + span):
                    keep[j] = False
                i += span
                matched = True
                break
        if not matched:
            i += 1
    return [s for (s, t), k in zip(pairs, keep) if k and _KEEP_TAG.match(t)]


def get_tokenizer(kind: str = "auto", user_dic_path: str | None = None) -> Tokenizer:
    """Build a tokenizer.

    Args:
        kind: "mecab", "simple", or "auto" (MeCab if importable, else simple).
        user_dic_path: Compiled user dictionary for the MeCab backend.

    Returns:
        A tokenizer instance.

    Raises:
        ValueError: If ``kind`` is unknown.
        ImportError: If ``kind == "mecab"`` but MeCab is unavailable.
    """
    if kind not in {"auto", "mecab", "simple"}:
        raise ValueError(f"unknown tokenizer kind: {kind!r}")
    if kind == "simple":
        return SimpleTokenizer()
    try:
        return MecabTokenizer(user_dic_path)
    except ImportError:
        if kind == "mecab":
            raise
        logger.info("MeCab unavailable; falling back to SimpleTokenizer")
        return SimpleTokenizer()


def remove_stopwords(
    tokens: Iterable[str], stopwords: set[str], max_span: int = 3
) -> list[str]:
    """Drop option/decoration tokens (e.g. 세트, 곱빼기, 시그니처, ICE).

    Matching is *span-aware*: a stopword is removed when it equals a single
    token **or** the concatenation of up to ``max_span`` adjacent tokens.
    This makes removal robust to morphological over-segmentation - MeCab
    splits 시그니처 into 시그/니/처 and 단품 into 단/품, which would slip
    past naive token-level matching. Substrings inside a longer single token
    are still never touched, so e.g. 대왕카스테라 is safe from the size
    stopword 대.
    """
    toks = list(tokens)
    out: list[str] = []
    i = 0
    while i < len(toks):
        span_matched = False
        for span in range(min(max_span, len(toks) - i), 0, -1):
            if "".join(toks[i : i + span]) in stopwords:
                i += span
                span_matched = True
                break
        if not span_matched:
            out.append(toks[i])
            i += 1
    return out
