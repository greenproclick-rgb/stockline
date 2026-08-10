import logging
import time
from datetime import date, datetime, timedelta
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
                "rsi": metric.get("rsi14") or metric.get("rsi"),
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
                    "url": item.get("url"),
                    "source": item.get("source"),
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
                    "url": item.get("url"),
                    "source": item.get("source"),
                }
                for item in (news or [])[:5]
            ]
        except Exception as e:
            self.logger.error(f"Error fetching market news: {e}")
            return None

    def get_historical_performance(
        self,
        symbol: str,
        days_back: int,
        period_label: Optional[str] = None,
        resolution: str = "D",
    ) -> Optional[Dict]:
        """Get historical performance for a stock over a lookback window."""
        try:
            to_date = date.today()
            from_date = to_date - timedelta(days=days_back)
            start_ts = int(datetime.combine(from_date, datetime.min.time()).timestamp())
            end_ts = int(datetime.combine(to_date, datetime.min.time()).timestamp())
            candles = self.client.stock_candles(symbol, resolution, start_ts, end_ts)
            closes = (candles or {}).get("c") or []
            highs = (candles or {}).get("h") or []
            lows = (candles or {}).get("l") or []

            if (candles or {}).get("s") != "ok" or len(closes) < 2:
                return None

            start_price = closes[0]
            end_price = closes[-1]
            if start_price in (None, 0) or end_price is None:
                return None

            absolute_change = end_price - start_price
            percent_change = (absolute_change / start_price) * 100
            return {
                "symbol": symbol,
                "period": period_label or f"{days_back}-day period",
                "start_price": start_price,
                "end_price": end_price,
                "absolute_change": absolute_change,
                "percent_change": percent_change,
                "high": max(highs) if highs else None,
                "low": min(lows) if lows else None,
            }
        except Exception as e:
            self.logger.error(f"Error fetching historical performance for {symbol}: {e}")
            return None

    def get_multi_period_performance(self, symbol: str) -> Dict[str, Dict]:
        """Get week, month, and quarter performance snapshots for a symbol."""
        periods = {
            "week": 7,
            "month": 30,
            "quarter": 90,
        }
        results: Dict[str, Dict] = {}
        for label, days_back in periods.items():
            performance = self.get_historical_performance(symbol, days_back, period_label=label)
            if performance:
                results[label] = performance
        return results

    def get_earnings_summary(self, symbol: str, days_forward: int = 120) -> Optional[Dict]:
        """Get the nearest earnings date and summary details when available."""
        try:
            from_date = date.today()
            to_date = from_date + timedelta(days=days_forward)
            data = self.client.earnings_calendar(
                _from=from_date.strftime("%Y-%m-%d"),
                to=to_date.strftime("%Y-%m-%d"),
                symbol=symbol,
            )
            calendar = (data or {}).get("earningsCalendar") or data or []
            if not calendar:
                return None

            entry = calendar[0]
            return {
                "symbol": symbol,
                "earnings_date": entry.get("date"),
                "eps_actual": entry.get("epsActual"),
                "eps_estimate": entry.get("epsEstimate"),
                "revenue_actual": entry.get("revenueActual"),
                "revenue_estimate": entry.get("revenueEstimate"),
                "hour": entry.get("hour"),
                "quarter": entry.get("quarter"),
                "year": entry.get("year"),
            }
        except Exception as e:
            self.logger.error(f"Error fetching earnings summary for {symbol}: {e}")
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
