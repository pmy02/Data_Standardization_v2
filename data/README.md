# Data

The original engagement data (~20M product records from a digital-platform
company, 2023) is covered by an NDA and **cannot be released**.

This repository instead ships:

| Path | Contents | Committed? |
|---|---|---|
| `data/lexicon/` | Canonical labels, stopwords, variant/translation maps, user-dictionary terms | yes |
| `data/sample/` | A 200-row sample of the synthetic benchmark for quick inspection | yes |
| `data/synthetic/` | Full synthetic benchmark — regenerate with `scripts/generate_synthetic.py` | no (gitignored) |

The synthetic benchmark is generated deterministically from a seed and
reproduces the documented noise modes of the original data (decorations,
options, spacing, code-switching, spelling variants, long-tail label
distribution, retail/non-food contamination). All numbers in the README are
measured on this open benchmark.
