#!/usr/bin/env python3
"""Run the standardization pipeline end to end.

Usage:
    python scripts/run_pipeline.py --config configs/default.yaml
    python scripts/run_pipeline.py --config configs/default.yaml \
        --input data/synthetic/menu_synthetic.csv --outdir results/exp1
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from menunorm.pipeline import load_config, run_pipeline

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/default.yaml")
    parser.add_argument("--input", type=Path, default=None, help="override config input CSV")
    parser.add_argument("--outdir", type=Path, default=None, help="override config output dir")
    parser.add_argument("--threshold", type=float, default=None, help="override match threshold")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_config(args.config)
    if args.input:
        config["input"] = str(args.input)
    if args.outdir:
        config["output_dir"] = str(args.outdir)
    if args.threshold is not None:
        config["match"]["threshold"] = args.threshold

    metrics = run_pipeline(config)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
