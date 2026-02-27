"""
Binance Futures Testnet REST client.

Handles HMAC-SHA256 request signing, HTTP communication, and
low-level error parsing. All API credentials are loaded from
environment variables (or a .env file via python-dotenv).

Environment variables required:
    BINANCE_TESTNET_API_KEY    – your Testnet API key
    BINANCE_TESTNET_API_SECRET – your Testnet API secret
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
import urllib.parse
from typing import Any

import requests
from dotenv import load_dotenv

from .logging_config import get_logger

load_dotenv()  # reads .env in the current working directory if present

BASE_URL = "https://testnet.binancefuture.com"
RECV_WINDOW = 5000  # milliseconds

logger = get_logger(__name__)


class BinanceAPIError(Exception):
    """Raised when the Binance API returns a non-2xx response or an error payload."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceFuturesClient:
    """Thin wrapper around the Binance USDT-M Futures REST API (Testnet)."""

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str = BASE_URL,
        timeout: int = 10,
    ) -> None:
        self.api_key = api_key or os.environ.get("BINANCE_TESTNET_API_KEY", "")
        self.api_secret = api_secret or os.environ.get("BINANCE_TESTNET_API_SECRET", "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        if not self.api_key or not self.api_secret:
            raise EnvironmentError(
                "BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_API_SECRET must be set "
                "(environment variables or .env file)."
            )

        self._session = requests.Session()
        self._session.headers.update({"X-MBX-APIKEY": self.api_key})
        logger.debug("BinanceFuturesClient initialised (base_url=%s)", self.base_url)

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _sign(self, params: dict) -> str:
        """Return HMAC-SHA256 hex-digest signature for the given params dict."""
        query_string = urllib.parse.urlencode(params)
        return hmac.new(
            key=self.api_secret.encode("utf-8"),
            msg=query_string.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

    def _signed_params(self, params: dict) -> dict:
        """Attach timestamp + recvWindow then append signature."""
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = RECV_WINDOW
        params["signature"] = self._sign(params)
        return params

    def _handle_response(self, response: requests.Response) -> Any:
        """Parse JSON and raise BinanceAPIError on failures."""
        logger.debug("HTTP %s %s → %s", response.request.method, response.url, response.status_code)
        try:
            payload = response.json()
        except Exception:
            response.raise_for_status()
            return {}

        if isinstance(payload, dict) and "code" in payload and int(payload["code"]) < 0:
            code = int(payload["code"])
            msg = payload.get("msg", "unknown error")
            logger.error("Binance error code=%d msg=%s", code, msg)
            raise BinanceAPIError(code, msg)

        if not response.ok:
            raise BinanceAPIError(response.status_code, response.text)

        return payload

    # ------------------------------------------------------------------
    # public API methods
    # ------------------------------------------------------------------

    def get_server_time(self) -> int:
        """Return Binance server time in milliseconds (unsigned endpoint)."""
        url = f"{self.base_url}/fapi/v1/time"
        resp = self._session.get(url, timeout=self.timeout)
        data = self._handle_response(resp)
        return data["serverTime"]

    def get_exchange_info(self, symbol: str | None = None) -> dict:
        """Return exchange information (unsigned)."""
        url = f"{self.base_url}/fapi/v1/exchangeInfo"
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        resp = self._session.get(url, params=params, timeout=self.timeout)
        return self._handle_response(resp)

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None = None,
        stop_price: float | None = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
    ) -> dict:
        """
        Place a new order on Binance Futures Testnet.

        Parameters
        ----------
        symbol      : Trading pair, e.g. 'BTCUSDT'
        side        : 'BUY' or 'SELL'
        order_type  : 'MARKET', 'LIMIT', 'STOP_MARKET', 'STOP', etc.
        quantity    : Order quantity in base asset
        price       : Limit price (required for LIMIT / STOP orders)
        stop_price  : Trigger price (required for STOP* orders)
        time_in_force: 'GTC', 'IOC', 'FOK' (only for LIMIT / STOP orders)
        reduce_only : Set True to make the order reduce-only
        """
        url = f"{self.base_url}/fapi/v1/order"

        params: dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": quantity,
        }

        if order_type.upper() in {"LIMIT", "STOP", "TAKE_PROFIT"}:
            params["timeInForce"] = time_in_force
            if price is not None:
                params["price"] = price

        if stop_price is not None:
            params["stopPrice"] = stop_price

        if reduce_only:
            params["reduceOnly"] = "true"

        signed = self._signed_params(params)

        logger.info(
            "Placing order → symbol=%s side=%s type=%s qty=%s price=%s stopPrice=%s",
            symbol,
            side,
            order_type,
            quantity,
            price,
            stop_price,
        )
        logger.debug("Request params (pre-signature): %s", {k: v for k, v in params.items() if k != "signature"})

        try:
            resp = self._session.post(url, params=signed, timeout=self.timeout)
            data = self._handle_response(resp)
        except requests.exceptions.ConnectionError as exc:
            logger.error("Network error while placing order: %s", exc)
            raise
        except requests.exceptions.Timeout as exc:
            logger.error("Request timed out while placing order: %s", exc)
            raise

        logger.info("Order placed successfully: orderId=%s status=%s", data.get("orderId"), data.get("status"))
        logger.debug("Full order response: %s", data)
        return data

    def get_order(self, symbol: str, order_id: int) -> dict:
        """Query an existing order by ID."""
        url = f"{self.base_url}/fapi/v1/order"
        params = self._signed_params({"symbol": symbol.upper(), "orderId": order_id})
        resp = self._session.get(url, params=params, timeout=self.timeout)
        return self._handle_response(resp)

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        """Cancel an open order by ID."""
        url = f"{self.base_url}/fapi/v1/order"
        params = self._signed_params({"symbol": symbol.upper(), "orderId": order_id})
        resp = self._session.delete(url, params=params, timeout=self.timeout)
        return self._handle_response(resp)

    def get_account(self) -> dict:
        """Return account information (balances, positions)."""
        url = f"{self.base_url}/fapi/v2/account"
        params = self._signed_params({})
        resp = self._session.get(url, params=params, timeout=self.timeout)
        return self._handle_response(resp)
