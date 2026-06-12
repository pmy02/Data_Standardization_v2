from menunorm.canonicalize import UNMATCHED, Canonicalizer

LABELS = ["아메리카노", "카페라떼", "김치찌개", "치즈돈가스", "떡볶이"]


def test_exact_match_fast_path():
    matcher = Canonicalizer(LABELS)
    out = matcher.match(["아메리카노"])
    row = out.iloc[0]
    assert row["pred_label"] == "아메리카노"
    assert row["method"] == "exact"
    assert row["score"] == 1.0


def test_spacing_noise_matches():
    matcher = Canonicalizer(LABELS)
    out = matcher.match(["아메리 카노", "치즈 돈가스"])
    assert list(out["pred_label"]) == ["아메리카노", "치즈돈가스"]


def test_abstention_on_out_of_lexicon():
    matcher = Canonicalizer(LABELS, threshold=0.45)
    out = matcher.match(["쿼크 글루온 플라즈마"])
    assert out.iloc[0]["pred_label"] == UNMATCHED


def test_empty_name():
    matcher = Canonicalizer(LABELS)
    out = matcher.match([""])
    assert out.iloc[0]["pred_label"] == UNMATCHED
    assert out.iloc[0]["method"] == "empty"
