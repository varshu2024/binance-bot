# -*- coding: utf-8 -*-
"""
CLI entry point for the Binance Futures Testnet Trading Bot.

Usage examples:
    # Market BUY
    python cli.py place-order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

    # Limit SELL
    python cli.py place-order --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 95000

    # Stop-Market BUY (bonus)
    python cli.py place-order --symbol BTCUSDT --side BUY --type STOP_MARKET --quantity 0.001 --stop-price 92000

    # TWAP BUY 0.01 BTC split into 5 slices every 30s (bonus)
    python cli.py twap --symbol BTCUSDT --side BUY --quantity 0.01 --slices 5 --interval 30

    # Interactive guided mode (bonus)
    python cli.py interactive

    # Dry-run (validate only, no order sent)
    python cli.py place-order --symbol BTCUSDT --side BUY --type LIMIT --quantity 0.001 --price 90000 --dry-run
"""

from __future__ import annotations

import argparse
import sys

from bot.logging_config import setup_logging, get_logger
from bot.client import BinanceFuturesClient, BinanceAPIError
from bot.orders import place_order, place_twap_order

# ---------------------------------------------------------------------------
setup_logging()
logger = get_logger(__name__)
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- place-order sub-command -------------------------------------------
    po = subparsers.add_parser(
        "place-order",
        help="Place a new futures order",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    po.add_argument(
        "--symbol", "-s",
        required=True,
        metavar="SYMBOL",
        help="Trading pair symbol, e.g. BTCUSDT",
    )
    po.add_argument(
        "--side",
        required=True,
        choices=["BUY", "SELL"],
        type=str.upper,
        help="Order side: BUY or SELL",
    )
    po.add_argument(
        "--type", "-t",
        dest="order_type",
        required=True,
        choices=["MARKET", "LIMIT", "STOP_MARKET", "STOP", "TAKE_PROFIT", "TAKE_PROFIT_MARKET"],
        type=str.upper,
        help="Order type",
    )
    po.add_argument(
        "--quantity", "-q",
        required=True,
        type=float,
        metavar="QTY",
        help="Order quantity in base asset",
    )
    po.add_argument(
        "--price", "-p",
        type=float,
        default=None,
        metavar="PRICE",
        help="Limit price (required for LIMIT / STOP orders)",
    )
    po.add_argument(
        "--stop-price",
        type=float,
        default=None,
        metavar="STOP_PRICE",
        help="Stop / trigger price (required for STOP* / TAKE_PROFIT* orders)",
    )
    po.add_argument(
        "--time-in-force", "-tif",
        default="GTC",
        choices=["GTC", "IOC", "FOK"],
        type=str.upper,
        help="Time-in-force for LIMIT orders (default: GTC)",
    )
    po.add_argument(
        "--reduce-only",
        action="store_true",
        default=False,
        help="Make this a reduce-only order",
    )
    po.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate inputs and print summary without sending the order",
    )

    # -- twap sub-command (bonus) -----------------------------------------
    tw = subparsers.add_parser(
        "twap",
        help="[BONUS] Execute a TWAP order (splits quantity into equal market slices)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    tw.add_argument(
        "--symbol", "-s",
        required=True,
        metavar="SYMBOL",
        help="Trading pair symbol, e.g. BTCUSDT",
    )
    tw.add_argument(
        "--side",
        required=True,
        choices=["BUY", "SELL"],
        type=str.upper,
        help="Order side: BUY or SELL",
    )
    tw.add_argument(
        "--quantity", "-q",
        required=True,
        type=float,
        metavar="QTY",
        help="Total quantity to split across all slices",
    )
    tw.add_argument(
        "--slices",
        required=True,
        type=int,
        metavar="N",
        help="Number of child MARKET orders (2-100)",
    )
    tw.add_argument(
        "--interval",
        required=True,
        type=int,
        metavar="SECONDS",
        help="Seconds between each slice execution (1-3600)",
    )
    tw.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show TWAP plan without placing any orders",
    )

    # -- interactive sub-command -------------------------------------------
    subparsers.add_parser(
        "interactive",
        help="Guided interactive mode - prompts for all values",
    )

    # -- account sub-command -----------------------------------------------
    subparsers.add_parser(
        "account",
        help="Show Binance Futures Testnet account summary",
    )

    return parser


# ---------------------------------------------------------------------------
# Interactive mode helpers
# ---------------------------------------------------------------------------

def _prompt(prompt_text: str, valid_choices: list[str] | None = None) -> str:
    """Prompt the user for input with optional choice validation."""
    while True:
        if valid_choices:
            formatted = "/".join(valid_choices)
            raw = input(f"  {prompt_text} [{formatted}]: ").strip()
            if raw.upper() in [c.upper() for c in valid_choices]:
                return raw.upper()
            print(f"  [!] Invalid choice. Must be one of: {formatted}")
        else:
            raw = input(f"  {prompt_text}: ").strip()
            if raw:
                return raw
            print("  [!] This field is required.")


def _prompt_float(prompt_text: str, required: bool = True) -> float | None:
    """Prompt for a positive float value."""
    while True:
        raw = input(f"  {prompt_text} (press Enter to skip): ").strip()
        if not raw:
            if required:
                print("  [!] This field is required.")
                continue
            return None
        try:
            val = float(raw)
            if val <= 0:
                print("  [!] Value must be > 0.")
                continue
            return val
        except ValueError:
            print("  [!] Please enter a valid number.")


def run_interactive(client: BinanceFuturesClient) -> None:
    """Guided interactive order placement."""
    print("\n" + "=" * 55)
    print("  Binance Futures Testnet Bot  --  Interactive Mode")
    print("=" * 55)

    symbol = _prompt("Symbol (e.g. BTCUSDT)").upper()
    side = _prompt("Side", ["BUY", "SELL"])
    order_type = _prompt(
        "Order Type",
        ["MARKET", "LIMIT", "STOP_MARKET", "STOP", "TAKE_PROFIT", "TAKE_PROFIT_MARKET"],
    )
    quantity = _prompt_float("Quantity", required=True)

    price = None
    stop_price = None
    time_in_force = "GTC"

    if order_type in {"LIMIT", "STOP", "TAKE_PROFIT"}:
        price = _prompt_float("Limit Price", required=True)
        time_in_force = _prompt("Time In Force", ["GTC", "IOC", "FOK"])

    if order_type in {"STOP_MARKET", "STOP", "TAKE_PROFIT", "TAKE_PROFIT_MARKET"}:
        stop_price = _prompt_float("Stop Price", required=True)

    reduce_only_raw = _prompt("Reduce Only?", ["Y", "N"])
    reduce_only = reduce_only_raw == "Y"

    dry_run_raw = _prompt("Dry Run (validate only, no order sent)?", ["Y", "N"])
    dry_run = dry_run_raw == "Y"

    place_order(
        client=client,
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        stop_price=stop_price,
        time_in_force=time_in_force,
        reduce_only=reduce_only,
        dry_run=dry_run,
    )


def run_account(client: BinanceFuturesClient) -> None:
    """Fetch and display a brief account summary."""
    print("\n  Fetching account info ...")
    try:
        data = client.get_account()
    except Exception as exc:
        print(f"  [ERROR] Could not fetch account: {exc}")
        sys.exit(1)

    print("\n" + "=" * 55)
    print("  ACCOUNT SUMMARY (Testnet)")
    print("=" * 55)
    print(f"  Total Wallet Balance : {data.get('totalWalletBalance', 'N/A')} USDT")
    print(f"  Available Balance    : {data.get('availableBalance', 'N/A')} USDT")
    print(f"  Total Unrealised PnL : {data.get('totalUnrealizedProfit', 'N/A')} USDT")
    print(f"  Can Trade            : {data.get('canTrade', 'N/A')}")
    print("=" * 55)
    logger.info(
        "Account balance=%s available=%s",
        data.get("totalWalletBalance"),
        data.get("availableBalance"),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    logger.info("Command: %s | Args: %s", args.command, vars(args))

    # For dry-run 'place-order', skip client entirely (no keys needed)
    if args.command == "place-order" and getattr(args, "dry_run", False):
        try:
            place_order(
                client=None,  # not used in dry-run
                symbol=args.symbol,
                side=args.side,
                order_type=args.order_type,
                quantity=args.quantity,
                price=args.price,
                stop_price=getattr(args, "stop_price", None),
                time_in_force=args.time_in_force,
                reduce_only=args.reduce_only,
                dry_run=True,
            )
        except ValueError:
            sys.exit(1)
        return

    # For dry-run 'twap', also skip client (validation + plan only)
    if args.command == "twap" and getattr(args, "dry_run", False):
        try:
            place_twap_order(
                client=None,  # not used in dry-run
                symbol=args.symbol,
                side=args.side,
                quantity=args.quantity,
                slices=args.slices,
                interval_seconds=args.interval,
                dry_run=True,
            )
        except ValueError:
            sys.exit(1)
        return

    # Initialise client (raises EnvironmentError if keys missing)
    try:
        client = BinanceFuturesClient()
    except EnvironmentError as exc:
        print(f"\n[CONFIG ERROR] {exc}")
        logger.critical("Client initialisation failed: %s", exc)
        sys.exit(1)

    try:
        if args.command == "place-order":
            place_order(
                client=client,
                symbol=args.symbol,
                side=args.side,
                order_type=args.order_type,
                quantity=args.quantity,
                price=args.price,
                stop_price=args.stop_price,
                time_in_force=args.time_in_force,
                reduce_only=args.reduce_only,
                dry_run=False,
            )

        elif args.command == "twap":
            place_twap_order(
                client=client,
                symbol=args.symbol,
                side=args.side,
                quantity=args.quantity,
                slices=args.slices,
                interval_seconds=args.interval,
                dry_run=False,
            )

        elif args.command == "interactive":
            run_interactive(client)

        elif args.command == "account":
            run_account(client)

    except ValueError:
        # Already printed by orders.place_order
        sys.exit(1)
    except BinanceAPIError:
        # Already printed
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(0)
    except Exception as exc:
        logger.exception("Unhandled exception: %s", exc)
        print(f"\n[FATAL] Unhandled error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
