import pytest

from menunorm.dictionary import build_user_dictionary_csv, has_jongseong, to_mecab_csv_row


def test_jongseong_detection():
    assert has_jongseong("강")          # ends in ㅇ
    assert has_jongseong("탕")
    assert not has_jongseong("노")      # open syllable
    assert has_jongseong("플")          # ends in ㄹ


def test_jongseong_non_hangul():
    assert not has_jongseong("a")
    with pytest.raises(ValueError):
        has_jongseong("ab")


def test_mecab_csv_row_format():
    row = to_mecab_csv_row("아인슈페너")
    fields = row.split(",")
    assert len(fields) == 12
    assert fields[0] == "아인슈페너"
    assert fields[6] == "F"            # 너 has no final consonant
    assert to_mecab_csv_row("콜드브루").split(",")[6] == "F"
    assert to_mecab_csv_row("마라탕").split(",")[6] == "T"


def test_build_csv(tmp_path):
    path = build_user_dictionary_csv(["크로플", "마라탕"], tmp_path / "dict.csv")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("크로플,")
