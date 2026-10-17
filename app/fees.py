MIN_AMOUNT = 10  # XAF


def compute_fee(amount: int, bps: int) -> int:
    """Fee in XAF, rounded up, never more than amount - 1 (a ledger line must stay > 0)."""
    if bps <= 0 or amount <= 1:
        return 0
    fee = (amount * bps + 9_999) // 10_000
    return min(fee, amount - 1)
