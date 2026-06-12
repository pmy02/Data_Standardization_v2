"""Synthetic benchmark generator for Korean product-name standardization.

The original engagement data is under NDA, so this module generates an *open*
benchmark that reproduces the noise modes documented during that project:

* decoration symbols and promo tags         ★아메리카노★, [인기] 김치찌개
* option/quantity suffixes                  떡볶이 세트, 짜장면곱빼기, +치즈추가
* temperature prefixes (beverages)          ICE 아메리카노, 핫 카페라떼
* spacing variants                          아메리 카노, 치즈돈가스
* Korean/English code-switching             cheese돈가스, 불고기 burger
* spelling variants                         돈까스, 라테, 케익
* store-branch prefixes                     [강남점] 물냉면
* a Zipf (long-tail) label distribution, matching the EDA finding that
  motivated the original project
* retail rows with *valid* EAN-13 barcodes and rows from non-food stores,
  which the stage-0 filter must remove (gold label ``NOT_TARGET``)

Every row carries a gold label, so the full pipeline is quantitatively
evaluable end to end.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd

from menunorm.barcode import ean13_check_digit

NOT_TARGET = "NOT_TARGET"

_DECORATIONS = [
    "★{}★", "♥{}♥", "▶{}◀", "☆{}☆", "{}!!", "[인기] {}", "{} (BEST)",
    "☆신메뉴☆ {}", "{} ♡추천♡", "시그니처 {}", "{} 주문폭주",
]
_OPTIONS = [
    "{} 세트", "{} 셋트", "{}세트", "{} 단품", "{} (곱빼기)", "{}곱빼기",
    "{} +치즈추가", "{} +사리추가", "{} 1+1", "{} (2인)", "{} 라지",
    "{} (L)", "{} (포장)", "{} (매운맛)", "{} 2개", "{} 1인분",
]
_TEMPS = ["ICE {}", "HOT {}", "아이스 {}", "핫 {}", "아이스{}"]
_BRANCHES = ["[강남점] {}", "(본점) {}", "[2호점] {}", "홍대점 {}"]
_QUANTITIES = ["{} 500ml", "{} 1L", "{} 350g"]

# canonical spelling -> common variant/typo (inverse of variant_map.csv)
_TYPO = {
    "돈가스": "돈까스", "라떼": "라테", "케이크": "케익", "샌드위치": "샌드윗치",
    "떡볶이": "떡볶기", "크루아상": "크로와상", "도넛": "도너츠", "리조또": "리조토",
}
# Korean component -> English alias (inverse of translation_map.csv)
_ENGLISH = {
    "치즈": "cheese", "초코": "choco", "딸기": "strawberry", "버거": "burger",
    "피자": "pizza", "치킨": "chicken", "떡볶이": "tteokbokki", "김밥": "gimbap",
    "토스트": "toast", "와플": "waffle", "베이글": "bagel", "도넛": "donut",
    "크로플": "croffle", "우동": "udon", "파스타": "pasta", "아메리카노": "americano",
    "불고기": "bulgogi", "새우": "shrimp", "마늘": "garlic",
}

_FOOD_CATEGORIES = ["카페", "한식", "중식", "일식", "양식", "분식", "치킨", "버거", "간식"]
_NONFOOD_CATEGORIES = ["편의점", "마트"]


def _make_ean13(rng: np.random.Generator) -> str:
    digits12 = "880" + "".join(str(rng.integers(0, 10)) for _ in range(9))
    return digits12 + str(ean13_check_digit(digits12))


def _corrupt(name: str, rng: np.random.Generator) -> str:
    """Apply one character-level typo: delete, transpose, or duplicate.

    Used only on the *hard* track. These corruptions are deliberately **not**
    covered by any lexicon (variant map, glossary, stopwords), so they probe
    genuine fuzzy-matching robustness rather than lookup coverage.
    """
    chars = list(name)
    hangul_idx = [i for i, c in enumerate(chars) if "가" <= c <= "힣"]
    if len(hangul_idx) < 3:
        return name
    i = int(rng.choice(hangul_idx))
    op = int(rng.integers(0, 3))
    if op == 0:
        del chars[i]
    elif op == 1 and i + 1 in hangul_idx:
        chars[i], chars[i + 1] = chars[i + 1], chars[i]
    else:
        chars.insert(i, chars[i])
    return "".join(chars)


def _apply_noise(name: str, category: str, rng: np.random.Generator) -> str:
    """Apply 0-3 independent noise operations to a canonical name."""
    if category == "카페" and rng.random() < 0.25:
        name = rng.choice(_TEMPS).format(name)
    if rng.random() < 0.20:
        for canon, typo in _TYPO.items():
            if canon in name:
                name = name.replace(canon, typo)
                break
    if rng.random() < 0.15:
        for kor, eng in _ENGLISH.items():
            if kor in name:
                name = name.replace(kor, eng)
                break
    if rng.random() < 0.30:
        name = rng.choice(_OPTIONS).format(name)
    if rng.random() < 0.25:
        name = rng.choice(_DECORATIONS).format(name)
    if rng.random() < 0.10:
        name = rng.choice(_BRANCHES).format(name)
    if rng.random() < 0.08:
        name = rng.choice(_QUANTITIES).format(name)
    if rng.random() < 0.20:
        chars = list(name)
        if len(chars) > 3:
            pos = int(rng.integers(1, len(chars) - 1))
            if chars[pos] != " " and chars[pos - 1] != " ":
                chars.insert(pos, " ")
            name = "".join(chars)
    return name


def load_canonical_labels(path: str | Path) -> pd.DataFrame:
    """Load the canonical label inventory (columns: label, category)."""
    return pd.read_csv(path)


def generate(
    n_rows: int,
    labels: pd.DataFrame,
    retail_names: list[str],
    seed: int = 42,
    zipf_s: float = 1.05,
    retail_rate: float = 0.06,
    nonfood_rate: float = 0.04,
    hard: bool = False,
    corrupt_rate: float = 0.12,
) -> pd.DataFrame:
    """Generate a synthetic raw product table.

    Args:
        n_rows: Number of rows to generate.
        labels: DataFrame with ``label`` and ``category`` columns.
        retail_names: Packaged retail product names (filter targets).
        seed: RNG seed (the benchmark is fully deterministic given the seed).
        zipf_s: Zipf exponent for the long-tail label distribution.
        retail_rate: Share of rows that are retail goods with valid EAN-13.
        nonfood_rate: Share of rows from non-food stores.
        hard: Enable the hard track - additional character-level typos that
            no lexicon covers (see :func:`_corrupt`).
        corrupt_rate: Per-row corruption probability on the hard track.

    Returns:
        DataFrame with columns ``store_id``, ``store_category``, ``barcode``,
        ``raw_name``, ``gold_label``.
    """
    rng = np.random.default_rng(seed)
    label_rows = labels.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    ranks = np.arange(1, len(label_rows) + 1, dtype=float)
    weights = 1.0 / ranks**zipf_s
    weights /= weights.sum()

    records: list[dict[str, str]] = []
    for _ in range(n_rows):
        roll = rng.random()
        if roll < nonfood_rate:
            # Non-food store: removed by the category filter regardless of name.
            name = str(rng.choice(retail_names))
            records.append(
                {
                    "store_id": f"S{rng.integers(0, 2000):04d}",
                    "store_category": str(rng.choice(_NONFOOD_CATEGORIES)),
                    "barcode": _make_ean13(rng) if rng.random() < 0.7 else "",
                    "raw_name": name,
                    "gold_label": NOT_TARGET,
                }
            )
        elif roll < nonfood_rate + retail_rate:
            # Retail item sold inside a food store: removed by barcode validity.
            name = str(rng.choice(retail_names))
            records.append(
                {
                    "store_id": f"S{rng.integers(0, 2000):04d}",
                    "store_category": str(rng.choice(_FOOD_CATEGORIES)),
                    "barcode": _make_ean13(rng),
                    "raw_name": name,
                    "gold_label": NOT_TARGET,
                }
            )
        else:
            idx = int(rng.choice(len(label_rows), p=weights))
            label = label_rows.loc[idx, "label"]
            category = label_rows.loc[idx, "category"]
            noisy = _apply_noise(label, category, rng)
            if hard and rng.random() < corrupt_rate:
                noisy = _corrupt(noisy, rng)
            records.append(
                {
                    "store_id": f"S{rng.integers(0, 2000):04d}",
                    "store_category": category,
                    "barcode": "" if rng.random() < 0.9 else f"M{rng.integers(0, 10**6):06d}",
                    "raw_name": noisy,
                    "gold_label": label,
                }
            )
    return pd.DataFrame.from_records(records)


def save(df: pd.DataFrame, path: str | Path) -> Path:
    """Write the generated table to CSV (UTF-8, fully quoted)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)
    return path
