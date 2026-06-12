"""menunorm: a reproducible standardization pipeline for noisy Korean product names.

The package reconstructs (and upgrades) a 2023 industry collaboration in which
~20M raw product records were standardized into ~1K canonical labels. The
original data is under NDA, so this package ships with a realistic synthetic
data generator and reports all benchmark numbers on that open data.
"""

from menunorm.barcode import validate_ean13
from menunorm.canonicalize import Canonicalizer
from menunorm.dictionary import build_user_dictionary_csv, has_jongseong
from menunorm.rules import RuleSet
from menunorm.tokenize import filter_tokens, get_tokenizer, remove_stopwords

__version__ = "1.0.0"

__all__ = [
    "Canonicalizer",
    "RuleSet",
    "filter_tokens",
    "build_user_dictionary_csv",
    "get_tokenizer",
    "has_jongseong",
    "remove_stopwords",
    "validate_ean13",
    "__version__",
]
