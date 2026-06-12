from menunorm.barcode import ean13_check_digit, validate_ean13


def test_known_valid_ean13():
    # Widely used reference example (Stabilo pen).
    assert validate_ean13("4006381333931")


def test_invalid_check_digit():
    assert not validate_ean13("4006381333932")


def test_malformed_inputs():
    assert not validate_ean13("400638133393")     # 12 digits
    assert not validate_ean13("abcdefghijklm")    # non-numeric
    assert not validate_ean13(None)               # not a string
    assert not validate_ean13("")                 # empty


def test_check_digit_roundtrip():
    digits12 = "880123456789"
    code = digits12 + str(ean13_check_digit(digits12))
    assert validate_ean13(code)
