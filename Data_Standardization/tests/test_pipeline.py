"""End-to-end smoke test on a small deterministic synthetic set."""
import json
from pathlib import Path

import pandas as pd
import pytest

from menunorm import synthetic
from menunorm.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def small_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("run")
    labels = synthetic.load_canonical_labels(ROOT / "data/lexicon/canonical_labels.csv")
    retail = pd.read_csv(ROOT / "data/lexicon/retail_products.csv")["name"].tolist()
    df = synthetic.generate(800, labels, retail, seed=7)
    input_csv = tmp / "input.csv"
    synthetic.save(df, input_csv)

    config = {
        "seed": 7,
        "input": str(input_csv),
        "lexicon_dir": str(ROOT / "data/lexicon"),
        "output_dir": str(tmp / "out"),
        "columns": {
            "store": "store_id", "category": "store_category",
            "barcode": "barcode", "name": "raw_name", "gold": "gold_label",
        },
        "filter": {"nonfood_categories": ["편의점", "마트"], "not_target_label": "NOT_TARGET"},
        "normalize": {"drop_residual_latin": True},
        "tokenizer": "auto",
        "user_dictionary": True,
        "match": {"ngram_min": 2, "ngram_max": 4, "threshold": 0.45},
        "discovery": {"max_clusters": 10},
    }
    metrics = run_pipeline(config)
    return metrics, tmp / "out"


def test_artifacts_exist(small_run):
    _, out = small_run
    for name in ["standardized.csv", "metrics.json", "threshold_sweep.csv",
                 "label_proposals.csv", "rule_trace_sample.csv"]:
        assert (out / name).exists(), name


def test_filter_removes_retail_and_nonfood(small_run):
    metrics, _ = small_run
    assert metrics["n_rows_removed_by_filter"] > 0
    # The stage-0 filter should remove nearly all NOT_TARGET rows.
    assert metrics["filter_leakage_rows"] <= metrics["n_rows_input"] * 0.01


def test_accuracy_floor(small_run):
    metrics, _ = small_run
    assert metrics["overall_accuracy"] > 0.90
    assert metrics["matched_accuracy"] > 0.95


def test_metrics_json_round_trip(small_run):
    metrics, out = small_run
    on_disk = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert on_disk["n_rows_input"] == metrics["n_rows_input"]


def test_simple_tokenizer_path(small_run, tmp_path):
    """The pipeline must stay runnable without MeCab (fallback parity)."""
    metrics, _ = small_run
    labels = synthetic.load_canonical_labels(ROOT / "data/lexicon/canonical_labels.csv")
    retail = pd.read_csv(ROOT / "data/lexicon/retail_products.csv")["name"].tolist()
    df = synthetic.generate(400, labels, retail, seed=11)
    input_csv = tmp_path / "input.csv"
    synthetic.save(df, input_csv)
    config = {
        "seed": 11,
        "input": str(input_csv),
        "lexicon_dir": str(ROOT / "data/lexicon"),
        "output_dir": str(tmp_path / "out_simple"),
        "columns": {
            "store": "store_id", "category": "store_category",
            "barcode": "barcode", "name": "raw_name", "gold": "gold_label",
        },
        "filter": {"nonfood_categories": ["편의점", "마트"], "not_target_label": "NOT_TARGET"},
        "normalize": {"drop_residual_latin": True},
        "tokenizer": "simple",
        "user_dictionary": False,
        "match": {"ngram_min": 2, "ngram_max": 4, "threshold": 0.45},
        "discovery": {"max_clusters": 10},
    }
    simple_metrics = run_pipeline(config)
    assert simple_metrics["tokenizer"] == "simple"
    assert simple_metrics["overall_accuracy"] > 0.85
