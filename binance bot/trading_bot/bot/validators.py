"""
Input validation helpers for CLI arguments passed to the trading bot.
Raises ValueError with a descriptive message on failure.
"""

from __future__ import annotations

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET", "STOP", "TAKE_PROFIT", "TAKE_PROFIT_MARKET"}


def validate_symbol(symbol: str) -> str:
    """Ensure symbol is a non-empty uppercase string (e.g. BTCUSDT)."""
    s = symbol.strip().upper()
    if not s:
        raise ValueError("Symbol must not be empty.")
    if not s.isalpha():
        raise ValueError(f"Symbol '{s}' should contain only alphabetic characters (e.g. BTCUSDT).")
    return s


def validate_side(side: str) -> str:
    """Validate order side is BUY or SELL."""
    s = side.strip().upper()
    if s not in VALID_SIDES:
        raise ValueError(f"Side must be one of {sorted(VALID_SIDES)}, got '{side}'.")
    return s


def validate_order_type(order_type: str) -> str:
    """Validate order type."""
    t = order_type.strip().upper()
    if t not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Order type must be one of {sorted(VALID_ORDER_TYPES)}, got '{order_type}'."
        )
    return t


def validate_quantity(quantity: str | float) -> float:
    """Validate quantity is a positive number."""
    try:
        q = float(quantity)
    except (TypeError, ValueError):
        raise ValueError(f"Quantity must be a positive number, got '{quantity}'.")
    if q <= 0:
        raise ValueError(f"Quantity must be > 0, got {q}.")
    return q


def validate_price(price: str | float | None, order_type: str) -> float | None:
    """
    Validate price:
    - Required (and > 0) for LIMIT / STOP orders.
    - Must be None (or omitted) for MARKET / STOP_MARKET / TAKE_PROFIT_MARKET.
    """
    needs_price = order_type in {"LIMIT", "STOP", "TAKE_PROFIT"}

    if needs_price:
        if price is None:
            raise ValueError(f"Price is required for {order_type} orders.")
        try:
            p = float(price)
        except (TypeError, ValueError):
            raise ValueError(f"Price must be a positive number, got '{price}'.")
        if p <= 0:
            raise ValueError(f"Price must be > 0, got {p}.")
        return p

    # Market-style orders – price should not be sent
    if price is not None:
        try:
            p = float(price)
            if p > 0:
                # warn-level: silently ignore but caller can log
                return None
        except (TypeError, ValueError):
            pass
    return None


def validate_stop_price(stop_price: str | float | None, order_type: str) -> float | None:
    """Validate stop-price for STOP / STOP_MARKET / TAKE_PROFIT / TAKE_PROFIT_MARKET orders."""
    needs_stop = order_type in {"STOP", "STOP_MARKET", "TAKE_PROFIT", "TAKE_PROFIT_MARKET"}
    if needs_stop:
        if stop_price is None:
            raise ValueError(f"--stop-price is required for {order_type} orders.")
        try:
            sp = float(stop_price)
        except (TypeError, ValueError):
            raise ValueError(f"Stop-price must be a positive number, got '{stop_price}'.")
        if sp <= 0:
            raise ValueError(f"Stop-price must be > 0, got {sp}.")
        return sp
    return None


def validate_all(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: str | float | None = None,
    stop_price: str | float | None = None,
) -> dict:
    """
    Run all validators and return a clean dict ready for the orders layer.
    Raises ValueError on the first failure encountered.
    """
    validated_type = validate_order_type(order_type)
    return {
        "symbol": validate_symbol(symbol),
        "side": validate_side(side),
        "order_type": validated_type,
        "quantity": validate_quantity(quantity),
        "price": validate_price(price, validated_type),
        "stop_price": validate_stop_price(stop_price, validated_type),
    }


def validate_twap_params(
    symbol: str,
    side: str,
    quantity: str | float,
    slices: int,
    interval_seconds: int,
) -> dict:
    """
    Validate TWAP-specific parameters.

    Parameters
    ----------
    symbol           : Trading pair, e.g. BTCUSDT
    side             : BUY or SELL
    quantity         : Total order quantity to split across slices
    slices           : Number of child orders (2-100)
    interval_seconds : Delay between each child order in seconds (1-3600)
    """
    validated_symbol = validate_symbol(symbol)
    validated_side = validate_side(side)
    total_qty = validate_quantity(quantity)

    if not isinstance(slices, int) or slices < 2 or slices > 100:
        raise ValueError(f"TWAP slices must be an integer between 2 and 100, got '{slices}'.")

    if not isinstance(interval_seconds, int) or interval_seconds < 1 or interval_seconds > 3600:
        raise ValueError(
            f"TWAP interval must be an integer between 1 and 3600 seconds, got '{interval_seconds}'."
        )

    slice_qty = round(total_qty / slices, 6)
    if slice_qty <= 0:
        raise ValueError(
            f"Slice quantity ({slice_qty}) is too small. "
            f"Increase total quantity or reduce number of slices."
        )

    return {
        "symbol": validated_symbol,
        "side": validated_side,
        "total_quantity": total_qty,
        "slices": slices,
        "interval_seconds": interval_seconds,
        "slice_quantity": slice_qty,
    }

