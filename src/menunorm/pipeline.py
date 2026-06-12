"""End-to-end standardization pipeline.

Stages
------
0. **Target filtering** - drop non-food stores and rows with a valid EAN-13
   barcode (packaged retail goods).
1. **Rule normalization** - declarative, ordered, traceable rules
   (:mod:`menunorm.rules`).
2. **Dual segmentation** - the configured tokenizer (MeCab with a compiled
   domain user dictionary when available) *and* a surface segmentation, each
   followed by span-aware stopword removal.
3. **Canonicalization with score fusion** - both candidate strings are scored
   against the canonical lexicon (exact + character-n-gram TF-IDF) and the
   higher-scoring one wins (ties prefer the surface candidate, which never
   loses characters). Scores below the abstention threshold yield
   ``UNMATCHED`` instead of a forced assignment.
4. **Evaluation & discovery** - gold-label metrics with a per-path ablation,
   threshold sweep, and cluster-based proposals for new canonical labels.

Why fusion: morphological analysis is brittle under spacing noise (MeCab
loses characters on 돼 지국밥) while surface n-grams are brittle when
morphology is genuinely needed; taking the per-row max of both scores keeps
the strengths of each, and the ablation in ``metrics.json`` quantifies the
contribution honestly.

Artifacts written to ``output_dir``: ``standardized.csv``, ``metrics.json``,
``threshold_sweep.csv``, ``label_proposals.csv``, ``rule_trace_sample.csv``.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from menunorm.barcode import validate_ean13
from menunorm.canonicalize import UNMATCHED, Canonicalizer
from menunorm.cluster import propose_labels
from menunorm.dictionary import build_user_dictionary_csv, compile_user_dictionary
from menunorm.evaluate import compute_metrics, threshold_sweep
from menunorm.rules import RuleSet
from menunorm.tokenize import SimpleTokenizer, filter_tokens, get_tokenizer

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------- config
def load_config(path: str | Path) -> dict[str, Any]:
    """Load a YAML config; relative paths resolve against the repo root.

    The repo root is taken to be the parent of the config file's directory
    (configs live in ``<root>/configs/``).
    """
    path = Path(path).resolve()
    with open(path, encoding="utf-8") as fh:
        config: dict[str, Any] = yaml.safe_load(fh)
    root = path.parent.parent
    for key in ("input", "lexicon_dir", "output_dir"):
        if key in config and not Path(config[key]).is_absolute():
            config[key] = str(root / config[key])
    return config


def _load_lexicons(lexicon_dir: Path) -> dict[str, Any]:
    labels = pd.read_csv(lexicon_dir / "canonical_labels.csv")
    stopwords = {
        line.strip()
        for line in (lexicon_dir / "stopwords.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    variants = pd.read_csv(lexicon_dir / "variant_map.csv")
    translations = pd.read_csv(lexicon_dir / "translation_map.csv")
    user_terms = [
        line.strip()
        for line in (lexicon_dir / "user_dictionary_terms.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    return {
        "labels": labels["label"].tolist(),
        "stopwords": stopwords,
        "variant_map": dict(zip(variants["variant"], variants["canonical"])),
        "translation_map": dict(zip(translations["english"], translations["korean"])),
        "user_terms": user_terms,
    }


# ------------------------------------------------------------------- pipeline
def run_pipeline(config: dict[str, Any]) -> dict[str, Any]:
    """Run all stages and write artifacts.

    Args:
        config: Parsed configuration (see ``configs/default.yaml``).

    Returns:
        The metrics dictionary that is also written to ``metrics.json``.
    """
    t_start = time.perf_counter()
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    lex = _load_lexicons(Path(config["lexicon_dir"]))
    cols = config["columns"]

    df = pd.read_csv(config["input"], dtype={cols["barcode"]: "string"})
    n_raw = len(df)

    # Stage 0 - target filtering ----------------------------------------------
    nonfood = set(config["filter"]["nonfood_categories"])
    category_mask = ~df[cols["category"]].isin(nonfood)
    barcode_mask = ~df[cols["barcode"]].map(validate_ean13)
    df = df[category_mask & barcode_mask].reset_index(drop=True)
    n_filtered = len(df)

    # Stage 1 - rule normalization --------------------------------------------
    rules = RuleSet(
        translation_map=lex["translation_map"],
        variant_map=lex["variant_map"],
        drop_residual_latin=config["normalize"]["drop_residual_latin"],
    )
    traced = df[cols["name"]].map(rules.apply_with_trace)
    df["normalized"] = [t[0] for t in traced]
    df["rules_fired"] = ["|".join(t[1]) for t in traced]

    # Stage 2 - dual segmentation + span-aware stopword removal ----------------
    user_dic = None
    if config.get("user_dictionary", True):
        csv_path = out_dir / "user_dictionary.csv"
        build_user_dictionary_csv(lex["user_terms"], csv_path)
        user_dic = compile_user_dictionary(csv_path, out_dir / "user_dictionary.dic")
    tokenizer = get_tokenizer(config.get("tokenizer", "auto"), user_dic)
    stop = lex["stopwords"]
    df["clean_token"] = df["normalized"].map(
        lambda s: " ".join(filter_tokens(tokenizer.analyze(s), stop))
    )
    if tokenizer.name == "simple":
        df["clean_surface"] = df["clean_token"]
    else:
        surface = SimpleTokenizer()
        df["clean_surface"] = df["normalized"].map(
            lambda s: " ".join(filter_tokens(surface.analyze(s), stop))
        )

    # Stage 3 - candidate scoring + fusion --------------------------------------
    matcher = Canonicalizer(
        lex["labels"],
        ngram_range=(config["match"]["ngram_min"], config["match"]["ngram_max"]),
        threshold=config["match"]["threshold"],
    )
    candidates = pd.unique(pd.concat([df["clean_token"], df["clean_surface"]]))
    lookup = matcher.score(list(candidates)).set_index("name")
    tok = lookup.loc[df["clean_token"]].reset_index(drop=True)
    sur = lookup.loc[df["clean_surface"]].reset_index(drop=True)

    prefer_surface = sur["score"].to_numpy() >= tok["score"].to_numpy()
    df["best_label"] = np.where(prefer_surface, sur["best_label"], tok["best_label"])
    df["score"] = np.where(prefer_surface, sur["score"], tok["score"])
    df["method"] = np.where(prefer_surface, sur["method"], tok["method"])
    df["match_path"] = np.where(prefer_surface, "surface", "token")
    df["clean_name"] = np.where(prefer_surface, df["clean_surface"], df["clean_token"])

    thr = config["match"]["threshold"]

    def _apply_threshold(best: pd.Series, score: pd.Series, method: pd.Series) -> np.ndarray:
        committed = (score.to_numpy() >= thr) & (method.to_numpy() != "empty")
        return np.where(committed, best, UNMATCHED)

    df["pred_label"] = _apply_threshold(df["best_label"], df["score"], df["method"])

    # Stage 4 - evaluation + discovery ------------------------------------------
    metrics: dict[str, Any] = {
        "n_rows_input": n_raw,
        "n_rows_after_filter": n_filtered,
        "n_rows_removed_by_filter": n_raw - n_filtered,
        "tokenizer": tokenizer.name,
        "user_dictionary_compiled": user_dic is not None,
        "threshold": thr,
    }
    gold_col = cols.get("gold")
    if gold_col and gold_col in df.columns:
        not_target = config["filter"].get("not_target_label", "NOT_TARGET")
        metrics["filter_leakage_rows"] = int((df[gold_col] == not_target).sum())
        eval_mask = df[gold_col] != not_target
        eval_df = df[eval_mask]
        metrics.update(
            compute_metrics(
                eval_df[gold_col], eval_df["pred_label"], raw_names=eval_df[cols["name"]]
            )
        )

        # Per-path ablation: what each segmentation achieves alone vs. fused.
        ablation: dict[str, dict[str, float]] = {}
        for name, frame in {"token_path": tok, "surface_path": sur}.items():
            pred = pd.Series(
                _apply_threshold(frame["best_label"], frame["score"], frame["method"]),
                index=df.index,
            )
            part = compute_metrics(eval_df[gold_col], pred[eval_mask])
            ablation[name] = {
                k: round(float(part[k]), 4)
                for k in ("coverage", "matched_accuracy", "overall_accuracy")
            }
        ablation["fused"] = {
            k: round(float(metrics[k]), 4)
            for k in ("coverage", "matched_accuracy", "overall_accuracy")
        }
        metrics["ablation"] = ablation

        sweep_frame = eval_df[["best_label", "score", "method"]].assign(gold=eval_df[gold_col])
        sweep = threshold_sweep(sweep_frame, thresholds=[round(0.05 * i, 2) for i in range(1, 19)])
        sweep.to_csv(out_dir / "threshold_sweep.csv", index=False)

    unmatched = df.loc[df["pred_label"] == UNMATCHED, "clean_name"].tolist()
    proposals = propose_labels(
        unmatched,
        max_clusters=config["discovery"]["max_clusters"],
        seed=config.get("seed", 42),
    )
    proposals.to_csv(out_dir / "label_proposals.csv", index=False)
    metrics["n_label_proposals"] = len(proposals)
    metrics["runtime_seconds"] = round(time.perf_counter() - t_start, 2)

    # Artifacts ------------------------------------------------------------------
    keep = [
        cols["store"], cols["category"], cols["name"], "normalized", "clean_name",
        "pred_label", "score", "method", "match_path", "rules_fired",
    ]
    if gold_col and gold_col in df.columns:
        keep.append(gold_col)
    df[keep].to_csv(out_dir / "standardized.csv", index=False)
    df[keep].sample(min(200, len(df)), random_state=0).to_csv(
        out_dir / "rule_trace_sample.csv", index=False
    )
    with open(out_dir / "metrics.json", "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=2)
    logger.info("pipeline finished: %s", metrics)
    return metrics
