"""MeCab user-dictionary construction for domain loanwords and neologisms.

Stock mecab-ko-dic over-segments food-domain loanwords (e.g. 아인슈페너 ->
아인 + 슈페너, 크로플 -> 크로 + 플). The original project fixed this with a
hand-filled spreadsheet; here the dictionary is generated from a plain word
list (``data/lexicon/user_dictionary_terms.txt``) and compiled automatically.

The mecab-ko-dic CSV row format used for nouns is::

    surface,,,,POS,semantic,has_jongseong(T/F),reading,type,first_pos,last_pos,expression

Final-consonant (jongseong) presence is derived arithmetically from Unicode:
a precomposed Hangul syllable U+AC00..U+D7A3 decomposes as
``(code - 0xAC00) = 21 * 28 * lead + 28 * vowel + tail`` where ``tail == 0``
means no jongseong. This removes the original dependency on the ``jamo``
package.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_HANGUL_BASE = 0xAC00
_HANGUL_LAST = 0xD7A3
_NUM_TAILS = 28


def has_jongseong(char: str) -> bool:
    """Return True if a single Hangul syllable ends in a final consonant.

    Non-Hangul characters return False.
    """
    if len(char) != 1:
        raise ValueError("expected a single character")
    code = ord(char)
    if not _HANGUL_BASE <= code <= _HANGUL_LAST:
        return False
    return (code - _HANGUL_BASE) % _NUM_TAILS != 0


def to_mecab_csv_row(word: str, pos: str = "NNP") -> str:
    """Render one mecab-ko-dic user-dictionary CSV row for ``word``."""
    jong = "T" if has_jongseong(word[-1]) else "F"
    return f"{word},,,,{pos},*,{jong},{word},*,*,*,*"


def build_user_dictionary_csv(words: list[str], csv_path: str | Path) -> Path:
    """Write a mecab-ko-dic user-dictionary CSV for ``words``.

    Args:
        words: Surface forms to register (typically domain nouns).
        csv_path: Output CSV path.

    Returns:
        The output path.
    """
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [to_mecab_csv_row(w.strip()) for w in words if w.strip()]
    csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return csv_path


def compile_user_dictionary(csv_path: str | Path, dic_path: str | Path) -> Path | None:
    """Compile a user-dictionary CSV into a binary ``.dic`` usable by MeCab.

    Uses the ``python -m mecab dict-index`` entry point shipped with
    python-mecab-ko. Returns the compiled path, or None if compilation is
    unavailable in the current environment (the pipeline then falls back to
    the stock dictionary).
    """
    csv_path, dic_path = Path(csv_path), Path(dic_path)
    dic_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "mecab", "dict-index",
        "--userdic", str(dic_path), str(csv_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.warning("user-dictionary compilation failed (%s); using stock dictionary", exc)
        return None
    return dic_path if dic_path.exists() else None
