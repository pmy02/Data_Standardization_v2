import pytest

from menunorm.rules import RuleSet


@pytest.fixture()
def rules():
    return RuleSet(
        translation_map={"americano": "아메리카노", "cheese": "치즈"},
        variant_map={"돈까스": "돈가스", "케익": "케이크"},
    )


def test_decoration_and_bracket_removal(rules):
    assert rules.apply("★[인기] 아메리카노★") == "아메리카노"


def test_glued_option_suffix(rules):
    assert rules.apply("짜장면곱빼기") == "짜장면"
    assert rules.apply("떡볶이세트") == "떡볶이"


def test_quantity_and_promo_patterns(rules):
    assert rules.apply("콜라 500ml 1+1") == "콜라"
    assert rules.apply("후라이드치킨 +치즈추가") == "후라이드치킨"


def test_variant_normalization(rules):
    assert rules.apply("치즈돈까스") == "치즈돈가스"
    assert rules.apply("초코케익") == "초코케이크"


def test_translation_then_latin_cleanup(rules):
    assert rules.apply("ICE Americano") == "아메리카노"
    assert rules.apply("cheese돈까스") == "치즈돈가스"


def test_missing_values(rules):
    assert rules.apply(None) == ""
    assert rules.apply("   ") == ""


def test_trace_reports_fired_stages(rules):
    _, trace = rules.apply_with_trace("★아메리카노 세트★")
    assert "decorations" in trace


def test_latin_internal_space_collapsed(rules):
    assert rules.apply("chee se돈까스") == "치즈돈가스"


def test_spaced_variant_recovered(rules):
    assert rules.apply("치즈 돈 까스") == "치즈돈가스"
