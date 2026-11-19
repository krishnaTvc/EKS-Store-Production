import pytest
from decimal import Decimal
from order_app.services.pricing_service import calculate_line_total, calculate_order_total


def test_calculate_line_total_basic():
    unit_price = Decimal("360.00")
    quantity = 3
    total = calculate_line_total(unit_price, quantity)
    assert total == Decimal("1080.00")


def test_calculate_line_total_decimal_precision():
    unit_price = Decimal("1400.50")
    quantity = 2
    total = calculate_line_total(unit_price, quantity)
    assert total == Decimal("2801.00")


def test_calculate_line_total_invalid_quantity():
    with pytest.raises(ValueError, match="Quantity must be positive"):
        calculate_line_total(Decimal("100.00"), 0)


def test_calculate_line_total_negative_price():
    with pytest.raises(ValueError, match="Unit price cannot be negative"):
        calculate_line_total(Decimal("-50.00"), 1)


def test_calculate_order_total():
    lines = [
        Decimal("360.00"),
        Decimal("1400.00"),
        Decimal("220.00")
    ]
    total = calculate_order_total(lines)
    assert total == Decimal("1980.00")
