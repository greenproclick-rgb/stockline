import logging
import time
from datetime import UTC, date, datetime, timedelta
from typing import Dict, List, Optional

import finnhub


class FinnhubClient:
    """Wrapper around finnhub-python with app-specific helpers."""

    # Fallback list only (used if dynamic universe fetch fails)
    _MOVER_SYMBOLS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL"]

    # In-memory cache for US symbols with market cap > $500M
    _US_500M_UNIVERSE_CACHE: Dict[str, object] = {"symbols": None, "expires_at": 0}

    def __init__(self, api_key: str):
        self.logger = logging.getLogger(__name__)
        self.client = finnhub.Client(api_key=api_key)

    def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get real-time quote for a stock symbol."""
        try:
            q = self.client.quote(symbol)
            if not q:
                return None
            return {
                "symbol": symbol,
                "current_price": q.get("c"),
                "high": q.get("h"),
                "low": q.get("l"),
                "open": q.get("o"),
                "previous_close": q.get("pc"),
                "timestamp": q.get("t"),
            }
        except Exception as e:
            self.logger.error(f"Error fetching quote for {symbol}: {e}")
            return None

    def get_basic_financials(self, symbol: str) -> Optional[Dict]:
        """Get basic financial metrics."""
        try:
            data = self.client.company_basic_financials(symbol, "all")
            metric = (data or {}).get("metric", {})
            return {
                "symbol": symbol,
                "52_week_high": metric.get("52WeekHigh"),
                "52_week_low": metric.get("52WeekLow"),
                "pe_ratio": metric.get("peTTM") or metric.get("peBasicExclExtraTTM"),
                "beta": metric.get("beta"),
            }
        except Exception as e:
            self.logger.error(f"Error fetching basic financials for {symbol}: {e}")
            return None

    def get_price_target(self, symbol: str) -> Optional[Dict]:
        """Get analyst average price target."""
        try:
            data = self.client.price_target(symbol)
            if not data:
                return None
            return {"symbol": symbol, "target_price": data.get("targetMean")}
        except Exception as e:
            self.logger.error(f"Error fetching price target for {symbol}: {e}")
            return None

    def get_recommendation_trends(self, symbol: str) -> Optional[Dict]:
        """Get recommendation trends from analysts."""
        try:
            data = self.client.recommendation_trends(symbol) or []
            if not data:
                return None
            latest = data[0]
            return {
                "symbol": symbol,
                "buy": latest.get("buy", 0),
                "strong_buy": latest.get("strongBuy", 0),
                "hold": latest.get("hold", 0),
                "sell": latest.get("sell", 0),
                "strong_sell": latest.get("strongSell", 0),
                "period": latest.get("period"),
            }
        except Exception as e:
            self.logger.error(f"Error fetching recommendation trends for {symbol}: {e}")
            return None

    def get_company_news(self, symbol: str, days_back: int = 7) -> Optional[List[Dict]]:
        """Get recent company news."""
        try:
            to_date = date.today()
            from_date = to_date - timedelta(days=days_back)
            news = self.client.company_news(
                symbol,
                _from=from_date.strftime("%Y-%m-%d"),
                to=to_date.strftime("%Y-%m-%d"),
            )
            return [
                {
                    "headline": item.get("headline", ""),
                    "summary": item.get("summary", ""),
                    "source": item.get("source", ""),
                    "url": item.get("url", ""),
                }
                for item in (news or [])[:5]
            ]
        except Exception as e:
            self.logger.error(f"Error fetching company news for {symbol}: {e}")
            return None

    def get_market_news(self, category: str = "general") -> Optional[List[Dict]]:
        """Get general market news headlines."""
        try:
            news = self.client.general_news(category, min_id=0)
            return [
                {
                    "headline": item.get("headline", ""),
                    "summary": item.get("summary", ""),
                    "source": item.get("source", ""),
                    "url": item.get("url", ""),
                }
                for item in (news or [])[:5]
            ]
        except Exception as e:
            self.logger.error(f"Error fetching market news: {e}")
            return None

    def get_historical_change(self, symbol: str, period: str) -> Optional[Dict]:
        """Get a minimal price-change summary for a named historical period."""
        period_days = {
            "week": 7,
            "month": 30,
            "quarter": 90,
        }

        days = period_days.get((period or "").lower())
        if not days:
            return None

        try:
            end_at = int(time.time())
            start_at = int((datetime.now(UTC) - timedelta(days=days)).timestamp())
            candles = self.client.stock_candles(symbol, "D", start_at, end_at)
            closes = (candles or {}).get("c") or []
            status = (candles or {}).get("s")

            if status != "ok" or len(closes) < 2:
                return None

            start_price = closes[0]
            end_price = closes[-1]
            if start_price in (None, 0) or end_price is None:
                return None

            change = end_price - start_price
            change_percent = (change / start_price) * 100
            return {
                "symbol": symbol,
                "period": period,
                "start_price": start_price,
                "end_price": end_price,
                "change": change,
                "change_percent": change_percent,
            }
        except Exception as e:
            self.logger.error(f"Error fetching historical change for {symbol}: {e}")
            return None

    def get_rsi(self, symbol: str) -> Optional[Dict]:
        """Get the latest RSI value when supported by the API client."""
        indicator_method = getattr(self.client, "technical_indicator", None)
        if not callable(indicator_method):
            return None

        end_at = int(time.time())
        start_at = int((datetime.now(UTC) - timedelta(days=30)).timestamp())

        try:
            try:
                data = indicator_method(symbol, "D", start_at, end_at, "rsi", {"timeperiod": 14})
            except TypeError:
                data = indicator_method(
                    symbol=symbol,
                    resolution="D",
                    _from=start_at,
                    to=end_at,
                    indicator="rsi",
                    indicator_fields={"timeperiod": 14},
                )

            values = (data or {}).get("rsi") or []
            if not values:
                return None
            return {"symbol": symbol, "value": float(values[-1])}
        except Exception as e:
            self.logger.error(f"Error fetching RSI for {symbol}: {e}")
            return None

    def get_earnings(self, symbol: str) -> Optional[Dict]:
        """Get the nearest earnings date and minimal summary information."""
        try:
            calendar_method = getattr(self.client, "earnings_calendar", None)
            if callable(calendar_method):
                from_date = date.today() - timedelta(days=30)
                to_date = date.today() + timedelta(days=180)
                raw = calendar_method(
                    _from=from_date.strftime("%Y-%m-%d"),
                    to=to_date.strftime("%Y-%m-%d"),
                    symbol=symbol,
                    international=False,
                )
                entries = (
                    (raw or {}).get("earningsCalendar")
                    or (raw or {}).get("earnings")
                    or (raw or {}).get("data")
                    or []
                )
                if entries:
                    item = entries[0]
                    return {
                        "symbol": symbol,
                        "date": item.get("date"),
                        "eps_actual": item.get("epsActual"),
                        "eps_estimate": item.get("epsEstimate"),
                        "revenue_actual": item.get("revenueActual"),
                        "revenue_estimate": item.get("revenueEstimate"),
                    }

            company_method = getattr(self.client, "company_earnings", None)
            if callable(company_method):
                try:
                    entries = company_method(symbol, limit=1) or []
                except TypeError:
                    entries = company_method(symbol) or []
                if entries:
                    item = entries[0]
                    return {
                        "symbol": symbol,
                        "date": item.get("date") or item.get("period"),
                        "eps_actual": item.get("actual"),
                        "eps_estimate": item.get("estimate"),
                        "revenue_actual": item.get("revenueActual"),
                        "revenue_estimate": item.get("revenueEstimate"),
                    }
        except Exception as e:
            self.logger.error(f"Error fetching earnings for {symbol}: {e}")

        return None

    def _get_us_symbols_over_500m(self, ttl_seconds: int = 3600) -> List[str]:
        """
        Build universe: US-listed stocks with market cap > $500M.
        Finnhub company_profile2.marketCapitalization is in millions.
        """
        now = time.time()
        cached_symbols = self._US_500M_UNIVERSE_CACHE.get("symbols")
        expires_at = self._US_500M_UNIVERSE_CACHE.get("expires_at", 0)

        if cached_symbols and now < expires_at:
            return cached_symbols  # type: ignore[return-value]

        symbols: List[str] = []
        try:
            all_us = self.client.stock_symbols("US") or []

            for row in all_us:
                sym = (row or {}).get("symbol")
                if not sym:
                    continue
                # Optional quick skip to avoid many non-standard tickers
                if "." in sym:
                    continue

                try:
                    profile = self.client.company_profile2(symbol=sym) or {}
                    market_cap_m = profile.get("marketCapitalization")
                    if market_cap_m is not None and float(market_cap_m) > 500:
                        symbols.append(sym)
                except Exception:
                    continue

            self._US_500M_UNIVERSE_CACHE["symbols"] = symbols
            self._US_500M_UNIVERSE_CACHE["expires_at"] = now + ttl_seconds
            return symbols
        except Exception as e:
            self.logger.error(f"Error building US >500M universe: {e}")
            return []

    def get_market_movers(self, side: str = "gainers", count: int = 3) -> Optional[List[Dict]]:
        """
        Compute market movers from US-listed symbols with market cap > $500M.
        Fallback to _MOVER_SYMBOLS if universe fetch fails.
        """
        try:
            universe = self._get_us_symbols_over_500m()
            if not universe:
                universe = self._MOVER_SYMBOLS

            candidates = []
            for sym in universe:
                quote = self.get_quote(sym)
                if (
                    quote
                    and quote.get("current_price")
                    and quote.get("previous_close")
                    and quote["previous_close"] != 0
                ):
                    pct = (
                        (quote["current_price"] - quote["previous_close"])
                        / quote["previous_close"]
                        * 100
                    )
                    candidates.append(
                        {
                            "symbol": sym,
                            "pct_change": pct,
                            "price": quote["current_price"],
                        }
                    )

            if not candidates:
                return None

            if side == "gainers":
                candidates.sort(key=lambda x: x["pct_change"], reverse=True)
            elif side == "losers":
                candidates.sort(key=lambda x: x["pct_change"])
            else:
                candidates.sort(key=lambda x: abs(x["pct_change"]), reverse=True)

            return candidates[:count]
        except Exception as e:
            self.logger.error(f"Error fetching market movers: {e}")
            return None
