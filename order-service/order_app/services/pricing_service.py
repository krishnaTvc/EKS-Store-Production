from decimal import Decimal, ROUND_HALF_UP


def calculate_line_total(unit_price: Decimal, quantity: int) -> Decimal:
    """
    Computes line item total using Decimal arithmetic.
    Rounds to 2 decimal places using standard ROUND_HALF_UP.
    """
    if quantity <= 0:
        raise ValueError(f"Quantity must be positive, got {quantity}")
    if unit_price < 0:
        raise ValueError(f"Unit price cannot be negative, got {unit_price}")

    raw_total = unit_price * Decimal(quantity)
    return raw_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_order_total(line_totals: list[Decimal]) -> Decimal:
    """Sums all line totals to compute the grand order total."""
    total = sum(line_totals, Decimal("0.00"))
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
