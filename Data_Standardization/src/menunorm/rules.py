"""Declarative, auditable text-normalization rules.

This module replaces the original workflow in which normalization rules were
edited by hand inside a notebook and the spreadsheet was re-saved as
"ver26.xlsx", "ver27.xlsx", ... Every rule now lives in configuration
(``configs/default.yaml`` + ``data/lexicon/``), is applied in a fixed order,
and can emit a per-string trace of which rules fired - so each transformation
is reviewable instead of being buried in notebook history.

Rule order:
    1. Unicode NFKC normalization + Latin lowercasing
    2. English -> Korean term translation (offline glossary)
    3. Bracketed content removal:  (...) [...] {...} <...>
    4. Decoration symbol stripping
    5. Option/quantity pattern removal (regex list from config)
    6. Spelling-variant normalization (variant map)
    7. Residual digit/Latin cleanup + whitespace squeeze
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_BRACKETS = re.compile(r"\([^)]*\)|\[[^\]]*\]|\{[^}]*\}|<[^>]*>|【[^】]*】|「[^」]*」")
_LATIN_WORD = re.compile(r"[a-z]+")
_WS = re.compile(r"\s+")

DEFAULT_DECORATIONS = "★☆♥♡●○◆◇▶◀■□▲△!?~^*#@$%&_=|/\\·,'\"`:;"

DEFAULT_OPTION_PATTERNS = [
    r"\d+\s*\+\s*\d+",                      # 1+1, 2+1 promotions
    r"\+\s*\S+\s*추가",                      # +치즈 추가
    r"\d+(?:\.\d+)?\s*(?:ml|l|g|kg|cc|oz)",  # quantities: 500ml, 2L
    r"\d+\s*(?:개|인분|인|pcs|조각|pc|p)",     # counts: 2개, 1인분
    r"(?:세트|셋트|셑|단품|곱빼기)$",          # glued option suffixes
    r"^[가-힣a-z0-9]{1,5}점(?=\s)",          # store-branch prefixes: 홍대점, 2호점
]


@dataclass
class RuleSet:
    """A fixed-order, configuration-driven normalization rule set.

    Attributes:
        translation_map: Lowercased English term -> Korean term.
        variant_map: Non-standard Korean spelling -> canonical spelling.
        option_patterns: Regex patterns whose matches are removed.
        decoration_chars: Individual characters stripped as decoration.
        drop_residual_latin: If True, Latin words not covered by the
            translation map are removed at the end (the original project
            ultimately kept Korean-only text).
    """

    translation_map: dict[str, str] = field(default_factory=dict)
    variant_map: dict[str, str] = field(default_factory=dict)
    option_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_OPTION_PATTERNS))
    decoration_chars: str = DEFAULT_DECORATIONS
    drop_residual_latin: bool = True

    def __post_init__(self) -> None:
        self._option_re = [re.compile(p, re.IGNORECASE) for p in self.option_patterns]
        # Longest-first so that "milktea" wins over "tea", "돈까스" over "까스".
        self._trans_keys = sorted(self.translation_map, key=len, reverse=True)
        self._variant_keys = sorted(self.variant_map, key=len, reverse=True)
        self._deco_table = str.maketrans({c: " " for c in self.decoration_chars})

    # ------------------------------------------------------------------ steps
    def _normalize_unicode(self, text: str) -> str:
        return unicodedata.normalize("NFKC", text).lower()

    def _translate(self, text: str) -> str:
        # Spacing noise can split a Latin alias ("ch oco라떼"); collapse
        # single spaces between Latin letters before glossary lookup.
        text = re.sub(r"(?<=[a-z]) (?=[a-z])", "", text)
        for key in self._trans_keys:
            if key in text:
                text = re.sub(rf"{re.escape(key)}", self.translation_map[key], text)
        return text

    def _strip_brackets(self, text: str) -> str:
        return _BRACKETS.sub(" ", text)

    def _strip_decorations(self, text: str) -> str:
        return text.translate(self._deco_table)

    def _strip_options(self, text: str) -> str:
        for pattern in self._option_re:
            text = pattern.sub(" ", text)
        return text

    def _apply_variants(self, text: str) -> str:
        for key in self._variant_keys:
            if key in text:
                text = text.replace(key, self.variant_map[key])
            else:
                # Spacing noise can split a variant ("크 로와상"); fall back
                # to the space-collapsed form when that recovers a match.
                collapsed = text.replace(" ", "")
                if key in collapsed:
                    text = collapsed.replace(key, self.variant_map[key])
        return text

    def _cleanup(self, text: str) -> str:
        text = re.sub(r"[\d+]+", " ", text)
        if self.drop_residual_latin:
            text = _LATIN_WORD.sub(" ", text)
        return _WS.sub(" ", text).strip()

    # ------------------------------------------------------------------- api
    def apply(self, text: object) -> str:
        """Normalize a single raw product name."""
        clean, _ = self.apply_with_trace(text)
        return clean

    def apply_with_trace(self, text: object) -> tuple[str, list[str]]:
        """Normalize a name and report which rule stages changed it.

        Args:
            text: Raw product name (non-strings are treated as missing).

        Returns:
            Tuple of (normalized text, list of stage names that fired).
        """
        if not isinstance(text, str) or not text.strip():
            return "", ["missing"]
        steps = [
            ("unicode", self._normalize_unicode),
            ("translate", self._translate),
            ("brackets", self._strip_brackets),
            ("decorations", self._strip_decorations),
            ("options", self._strip_options),
            ("variants", self._apply_variants),
            ("cleanup", self._cleanup),
        ]
        trace: list[str] = []
        current = text
        for name, fn in steps:
            after = fn(current)
            if after != current:
                trace.append(name)
            current = after
        return current.strip(), trace
