"""
Order placement logic – sits between the CLI and the raw API client.

Formats requests, prints human-readable summaries, and returns
structured result dictionaries so the CLI can display them cleanly.
"""

from __future__ import annotations

import time
from typing import Any

from .client import BinanceFuturesClient, BinanceAPIError
from .logging_config import get_logger
from .validators import validate_all, validate_twap_params


logger = get_logger(__name__)


def _fmt(value: Any, default: str = "N/A") -> str:
    """Return a readable string; fall back to *default* when None / empty."""
    if value is None or value == "":
        return default
    return str(value)


def print_request_summary(params: dict) -> None:
    """Pretty-print the order request parameters."""
    print("\n" + "=" * 50)
    print("  ORDER REQUEST SUMMARY")
    print("=" * 50)
    print(f"  Symbol     : {params['symbol']}")
    print(f"  Side       : {params['side']}")
    print(f"  Type       : {params['order_type']}")
    print(f"  Quantity   : {params['quantity']}")
    if params.get("price"):
        print(f"  Price      : {params['price']}")
    if params.get("stop_price"):
        print(f"  Stop Price : {params['stop_price']}")
    print("=" * 50)


def print_order_response(response: dict) -> None:
    """Pretty-print the order response from Binance."""
    print("\n" + "=" * 50)
    print("  ORDER RESPONSE")
    print("=" * 50)
    print(f"  Order ID     : {_fmt(response.get('orderId'))}")
    print(f"  Client OID   : {_fmt(response.get('clientOrderId'))}")
    print(f"  Symbol       : {_fmt(response.get('symbol'))}")
    print(f"  Status       : {_fmt(response.get('status'))}")
    print(f"  Side         : {_fmt(response.get('side'))}")
    print(f"  Type         : {_fmt(response.get('type'))}")
    print(f"  Orig Qty     : {_fmt(response.get('origQty'))}")
    print(f"  Executed Qty : {_fmt(response.get('executedQty'))}")
    print(f"  Avg Price    : {_fmt(response.get('avgPrice'))}")
    print(f"  Price        : {_fmt(response.get('price'))}")
    print(f"  Stop Price   : {_fmt(response.get('stopPrice'))}")
    print(f"  Time In Force: {_fmt(response.get('timeInForce'))}")
    print(f"  Reduce Only  : {_fmt(response.get('reduceOnly'))}")
    print(f"  Update Time  : {_fmt(response.get('updateTime'))}")
    print("=" * 50)


def place_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float | str,
    price: float | str | None = None,
    stop_price: float | str | None = None,
    reduce_only: bool = False,
    time_in_force: str = "GTC",
    dry_run: bool = False,
) -> dict:
    """
    Validate inputs, print the request summary, place the order via the
    Binance client, print the response, and return the raw API dict.

    Parameters
    ----------
    client       : Authenticated BinanceFuturesClient instance
    symbol       : e.g. 'BTCUSDT'
    side         : 'BUY' | 'SELL'
    order_type   : 'MARKET' | 'LIMIT' | 'STOP_MARKET' | 'STOP' | …
    quantity     : Order quantity
    price        : Limit price (required for LIMIT / STOP)
    stop_price   : Trigger price (required for STOP* orders)
    reduce_only  : Whether the order should be reduce-only
    time_in_force: 'GTC' | 'IOC' | 'FOK'
    dry_run      : If True, validate and print summary but do NOT send the order
    """
    # ── 1. Validate inputs ──
    try:
        params = validate_all(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )
    except ValueError as exc:
        logger.error("Validation failed: %s", exc)
        print(f"\n[ERROR] Validation failed: {exc}")
        raise

    print_request_summary(params)

    if dry_run:
        print("\n[DRY RUN] Order NOT submitted. Validation passed. ✓")
        logger.info("Dry run – order not submitted. Params=%s", params)
        return {"dry_run": True, **params}

    # ── 2. Place the order ──
    try:
        response = client.place_order(
            symbol=params["symbol"],
            side=params["side"],
            order_type=params["order_type"],
            quantity=params["quantity"],
            price=params["price"],
            stop_price=params["stop_price"],
            time_in_force=time_in_force,
            reduce_only=reduce_only,
        )
    except BinanceAPIError as exc:
        logger.error("Order placement failed: code=%s msg=%s", exc.code, exc.message)
        print(f"\n[FAILURE] Order rejected by Binance — code {exc.code}: {exc.message}")
        raise
    except Exception as exc:
        logger.error("Unexpected error during order placement: %s", exc)
        print(f"\n[FAILURE] Unexpected error: {exc}")
        raise

    # ── 3. Print result ──
    print_order_response(response)
    print("\n[SUCCESS] Order placed successfully!")
    return response


# ---------------------------------------------------------------------------
# BONUS: TWAP (Time-Weighted Average Price) order
# ---------------------------------------------------------------------------

def place_twap_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: float | str,
    slices: int,
    interval_seconds: int,
    dry_run: bool = False,
) -> list[dict]:
    """
    Execute a TWAP order by splitting the total quantity into equal slices
    and placing one MARKET order per slice at fixed time intervals.

    Why TWAP?
    - Reduces market impact of large orders.
    - Achieves a price closer to the time-weighted average over the period.

    Parameters
    ----------
    client           : Authenticated BinanceFuturesClient
    symbol           : e.g. 'BTCUSDT'
    side             : 'BUY' or 'SELL'
    quantity         : Total quantity to execute across all slices
    slices           : Number of child MARKET orders (2-100)
    interval_seconds : Seconds to wait between each child order (1-3600)
    dry_run          : If True, validate and show plan but do NOT place any orders
    """
    # ── 1. Validate ──
    try:
        params = validate_twap_params(
            symbol=symbol,
            side=side,
            quantity=quantity,
            slices=slices,
            interval_seconds=interval_seconds,
        )
    except ValueError as exc:
        logger.error("TWAP validation failed: %s", exc)
        print(f"\n[ERROR] TWAP validation failed: {exc}")
        raise

    total_duration_sec = (slices - 1) * interval_seconds

    print("\n" + "=" * 56)
    print("  TWAP ORDER PLAN")
    print("=" * 56)
    print(f"  Symbol          : {params['symbol']}")
    print(f"  Side            : {params['side']}")
    print(f"  Total Quantity  : {params['total_quantity']}")
    print(f"  Slices          : {params['slices']}")
    print(f"  Qty per Slice   : {params['slice_quantity']}")
    print(f"  Interval        : {params['interval_seconds']}s")
    print(f"  Total Duration  : ~{total_duration_sec}s ({total_duration_sec / 60:.1f} min)")
    print("=" * 56)

    logger.info(
        "TWAP plan: symbol=%s side=%s total_qty=%s slices=%s interval=%ss slice_qty=%s",
        params["symbol"], params["side"], params["total_quantity"],
        params["slices"], params["interval_seconds"], params["slice_quantity"],
    )

    if dry_run:
        print("\n[DRY RUN] TWAP order NOT submitted. Validation passed.")
        logger.info("TWAP dry run – no orders submitted.")
        return [{"dry_run": True, **params}]

    # ── 2. Execute slices ──
    results: list[dict] = []
    total_executed = 0.0
    total_cost = 0.0
    failed_slices: list[int] = []

    print(f"\n  Executing {slices} slices every {interval_seconds}s. Press Ctrl+C to abort.\n")

    try:
        for i in range(1, slices + 1):
            print(f"  [{i}/{slices}] Placing MARKET {params['side']} {params['slice_quantity']} {params['symbol']} ...", end=" ", flush=True)
            logger.info(
                "TWAP slice %d/%d: symbol=%s side=%s qty=%s",
                i, slices, params["symbol"], params["side"], params["slice_quantity"],
            )

            try:
                resp = client.place_order(
                    symbol=params["symbol"],
                    side=params["side"],
                    order_type="MARKET",
                    quantity=params["slice_quantity"],
                )
                results.append(resp)

                exec_qty = float(resp.get("executedQty") or 0)
                avg_price = float(resp.get("avgPrice") or 0)
                total_executed += exec_qty
                total_cost += exec_qty * avg_price

                print(f"OK  orderId={resp.get('orderId')} avgPrice={avg_price:.4f} execQty={exec_qty}")
                logger.info(
                    "TWAP slice %d/%d filled: orderId=%s avgPrice=%s execQty=%s",
                    i, slices, resp.get("orderId"), avg_price, exec_qty,
                )

            except BinanceAPIError as exc:
                failed_slices.append(i)
                print(f"FAILED  code={exc.code} msg={exc.message}")
                logger.error(
                    "TWAP slice %d/%d failed: code=%s msg=%s",
                    i, slices, exc.code, exc.message,
                )

            except Exception as exc:
                failed_slices.append(i)
                print(f"FAILED  error={exc}")
                logger.error("TWAP slice %d/%d unexpected error: %s", i, slices, exc)

            # Wait before next slice (skip wait after the last slice)
            if i < slices:
                time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\n\n  [ABORT] TWAP aborted by user (Ctrl+C).")
        logger.warning(
            "TWAP aborted by user after %d/%d slices. "
            "Total executed: %s %s",
            len(results), slices, total_executed, params["symbol"],
        )

    # ── 3. Final summary ──
    avg_fill_price = (total_cost / total_executed) if total_executed > 0 else 0.0

    print("\n" + "=" * 56)
    print("  TWAP EXECUTION SUMMARY")
    print("=" * 56)
    print(f"  Symbol           : {params['symbol']}")
    print(f"  Side             : {params['side']}")
    print(f"  Slices Attempted : {len(results) + len(failed_slices)}/{slices}")
    print(f"  Slices Filled    : {len(results)}")
    print(f"  Slices Failed    : {len(failed_slices)}{' ' + str(failed_slices) if failed_slices else ''}")
    print(f"  Total Executed   : {total_executed:.6f}")
    print(f"  Avg Fill Price   : {avg_fill_price:.4f}" if avg_fill_price else "  Avg Fill Price   : N/A")
    print(f"  Total Cost       : {total_cost:.4f} USDT" if total_cost else "  Total Cost       : N/A")
    print("=" * 56)

    logger.info(
        "TWAP complete: slices_filled=%d/%d total_executed=%s avg_price=%s",
        len(results), slices, total_executed, f"{avg_fill_price:.4f}" if avg_fill_price else "N/A",
    )

    if len(results) == slices:
        print("\n[SUCCESS] TWAP order fully executed!")
    elif results:
        print(f"\n[PARTIAL] TWAP partially executed: {len(results)}/{slices} slices filled.")
    else:
        print("\n[FAILURE] TWAP order failed: no slices executed.")

    return results

