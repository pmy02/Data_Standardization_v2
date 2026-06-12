"""EAN-13 barcode validation.

In the original engagement, rows carrying a *valid* EAN-13 barcode were
packaged retail goods (bottled drinks, snacks) rather than restaurant menu
items, so check-digit validation was used as a cheap, high-precision filter
to remove them from the standardization target set.
"""

from __future__ import annotations


def ean13_check_digit(digits12: str) -> int:
    """Compute the EAN-13 check digit for the first 12 digits.

    Args:
        digits12: String of exactly 12 numeric characters.

    Returns:
        The check digit (0-9).

    Raises:
        ValueError: If the input is not exactly 12 digits.
    """
    if len(digits12) != 12 or not digits12.isdigit():
        raise ValueError("expected exactly 12 numeric characters")
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits12))
    return (10 - total % 10) % 10


def validate_ean13(code: object) -> bool:
    """Return True if ``code`` is a syntactically valid EAN-13 barcode.

    Accepts any object; non-strings and malformed strings return False so the
    function can be applied directly to a raw DataFrame column.
    """
    if not isinstance(code, str):
        return False
    code = code.strip()
    if len(code) != 13 or not code.isdigit():
        return False
    return ean13_check_digit(code[:12]) == int(code[12])
