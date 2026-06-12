#!/usr/bin/env python3
"""Generate the synthetic standardization benchmark.

Usage:
    python scripts/generate_synthetic.py --n 20000 --seed 42 \
        --out data/synthetic/menu_synthetic.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from menunorm import synthetic

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=20_000, help="number of rows")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hard", action="store_true",
                        help="add character-level typos not covered by any lexicon")
    parser.add_argument("--out", type=Path, default=ROOT / "data/synthetic/menu_synthetic.csv")
    parser.add_argument(
        "--sample-out",
        type=Path,
        default=None,
        help="optionally also write the first 200 rows (committed sample)",
    )
    args = parser.parse_args()

    labels = synthetic.load_canonical_labels(ROOT / "data/lexicon/canonical_labels.csv")
    retail = pd.read_csv(ROOT / "data/lexicon/retail_products.csv")["name"].tolist()

    df = synthetic.generate(args.n, labels, retail, seed=args.seed, hard=args.hard)
    out = synthetic.save(df, args.out)
    print(f"wrote {len(df):,} rows -> {out}")
    print(f"  target rows : {(df['gold_label'] != synthetic.NOT_TARGET).sum():,}")
    print(f"  filter rows : {(df['gold_label'] == synthetic.NOT_TARGET).sum():,}")
    print(f"  unique raw  : {df['raw_name'].nunique():,}")

    if args.sample_out:
        synthetic.save(df.head(200), args.sample_out)
        print(f"wrote 200-row sample -> {args.sample_out}")


if __name__ == "__main__":
    main()
