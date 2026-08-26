import logging
import requests
from typing import Dict, List, Optional
from datetime import date, timedelta
import re
import finnhub


class FinnhubClient:
    """Wrapper around finnhub-python with app-specific helpers."""

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
                "pe_ratio": metric.get("peTTM"),
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
                {"headline": item.get("headline", ""), "summary": item.get("summary", "")}
                for item in (news or [])[:5]
            ]
        except Exception as e:
            self.logger.error(f"Error fetching company news for {symbol}: {e}")
            return None

    def get_market_news(self, category: str = "general") -> Optional[List[Dict]]:
        """Get general market news headlines."""
        try:
            news = self.client.general_news(category, min_id=0)
            return [{"headline": item.get("headline", "")} for item in (news or [])[:5]]
        except Exception as e:
            self.logger.error(f"Error fetching market news: {e}")
            return None

    def get_market_movers(self, side: str = "gainers", count: int = 3) -> Optional[List[Dict]]:
        """
        Get market movers using FMP API (instant, no slow loop needed).
        This is a placeholder - actual implementation uses FMPClient below.
        """
        self.logger.warning("Use FMPClient.get_market_movers() instead for fast S&P 500 movers")
        return None


class FMPClient:
    """Financial Modeling Prep API client for market movers."""
    
    BASE_URL = "https://financialmodelingprep.com/api/v3"
    
    def __init__(self, api_key: str):
        self.logger = logging.getLogger(__name__)
        self.api_key = api_key
        self.name = "fmp"
        self.last_request_meta = {}
    
    def get_market_movers(self, side: str = "gainers", count: int = 10) -> Optional[List[Dict]]:
        """
        Get top S&P 500 gainers, losers, or most active stocks.
        Uses FMP's pre-calculated market movers endpoint.
        
        Args:
            side: "gainers", "losers", or "actives"
            count: Number of results to return (default 10)
        
        Returns:
            List of dicts with symbol, pct_change, price
        """
        try:
            self.last_request_meta = {"provider": "fmp", "side": side, "status_code": None}
            if side == "gainers":
                endpoint = f"{self.BASE_URL}/stock_market/gainers"
            elif side == "losers":
                endpoint = f"{self.BASE_URL}/stock_market/losers"
            else:  # actives
                endpoint = f"{self.BASE_URL}/stock_market/actives"
            
            params = {"apikey": self.api_key}
            self.logger.info(f"Fetching {side} from FMP API")
            
            response = requests.get(endpoint, params=params, timeout=5)
            self.last_request_meta["status_code"] = response.status_code
            response.raise_for_status()
            
            data = response.json()
            if not data:
                self.logger.warning(f"No {side} data from FMP")
                self.last_request_meta["error_type"] = "empty_data"
                return None
            
            # Transform FMP response to our format
            movers = []
            for item in data[:count]:
                try:
                    movers.append({
                        "symbol": item.get("symbol"),
                        "pct_change": float(item.get("change", 0)),
                        "price": float(item.get("price", 0)),
                    })
                except (ValueError, TypeError):
                    continue
            
            self.logger.info(f"Returned {len(movers)} {side}")
            self.last_request_meta["result_count"] = len(movers)
            return movers if movers else None
        
        except requests.exceptions.Timeout:
            self.logger.error(f"FMP API timeout for {side}")
            self.last_request_meta["error_type"] = "upstream_timeout"
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"FMP API error for {side}: {e}")
            self.last_request_meta["error_type"] = "upstream_error"
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error fetching {side}: {e}")
            self.last_request_meta["error_type"] = "invalid_payload"
            return None


class AlphaVantageClient:
    """Alpha Vantage API client for market movers."""

    BASE_URL = "https://www.alphavantage.co/query"

    _SIDE_KEY_MAP = {
        "gainers": "top_gainers",
        "losers": "top_losers",
        "actives": "most_actively_traded",
    }

    def __init__(self, api_key: Optional[str]):
        self.logger = logging.getLogger(__name__)
        self.api_key = api_key
        self.name = "alphavantage"
        self.last_request_meta = {}

    @staticmethod
    def _parse_float(value) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = re.sub(r"[^0-9+.\-]", "", value)
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    def get_market_movers(self, side: str = "gainers", count: int = 10) -> Optional[List[Dict]]:
        self.last_request_meta = {"provider": "alphavantage", "side": side, "status_code": None}

        if not self.api_key:
            self.last_request_meta["error_type"] = "missing_key"
            self.logger.warning("Alpha Vantage API key missing for market movers request")
            return None

        key = self._SIDE_KEY_MAP.get(side)
        if not key:
            self.last_request_meta["error_type"] = "invalid_payload"
            return None

        try:
            response = requests.get(
                self.BASE_URL,
                params={"function": "TOP_GAINERS_LOSERS", "apikey": self.api_key},
                timeout=8,
            )
            self.last_request_meta["status_code"] = response.status_code
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, dict):
                self.last_request_meta["error_type"] = "invalid_payload"
                return None

            if payload.get("Note") or payload.get("Information") or payload.get("Error Message"):
                self.last_request_meta["error_type"] = "upstream_error"
                return None

            entries = payload.get(key)
            if not isinstance(entries, list) or not entries:
                self.last_request_meta["error_type"] = "empty_data"
                return None

            movers = []
            for item in entries[:count]:
                if not isinstance(item, dict):
                    continue
                symbol = item.get("ticker") or item.get("symbol")
                pct_change = self._parse_float(item.get("change_percentage"))
                price = self._parse_float(item.get("price"))
                if not symbol or pct_change is None:
                    continue
                movers.append({"symbol": symbol, "pct_change": pct_change, "price": price or 0.0})

            if not movers:
                self.last_request_meta["error_type"] = "empty_data"
                return None

            self.last_request_meta["result_count"] = len(movers)
            return movers

        except requests.exceptions.Timeout:
            self.last_request_meta["error_type"] = "upstream_timeout"
            self.logger.error("Alpha Vantage timeout while fetching movers for side=%s", side)
            return None
        except requests.exceptions.RequestException as e:
            self.last_request_meta["error_type"] = "upstream_error"
            self.logger.error("Alpha Vantage HTTP error for side=%s: %s", side, e)
            return None
        except ValueError:
            self.last_request_meta["error_type"] = "invalid_payload"
            self.logger.error("Alpha Vantage returned non-JSON payload for side=%s", side)
            return None
        except Exception as e:
            self.last_request_meta["error_type"] = "invalid_payload"
            self.logger.error("Unexpected Alpha Vantage payload issue for side=%s: %s", side, e)
            return None


class MarketMoversService:
    """Fetch market movers with provider fallback."""

    def __init__(self, providers: List):
        self.logger = logging.getLogger(__name__)
        self.providers = [p for p in providers if p is not None]

    def get_market_movers(self, side: str, count: int = 3) -> Optional[List[Dict]]:
        provider_attempt_order = []

        for provider in self.providers:
            provider_name = getattr(provider, "name", provider.__class__.__name__).lower()
            provider_attempt_order.append(provider_name)

            movers = provider.get_market_movers(side, count=count)
            meta = getattr(provider, "last_request_meta", {}) or {}
            status_code = meta.get("status_code")
            result_count = len(movers) if movers else 0
            error_type = meta.get("error_type")

            self.logger.info(
                "ivr.movers.provider_attempt provider=%s side=%s status=%s count=%s error_type=%s order=%s",
                provider_name,
                side,
                status_code,
                result_count,
                error_type,
                provider_attempt_order,
            )

            if movers:
                return movers

        self.logger.warning(
            "ivr.movers.providers_exhausted side=%s order=%s",
            side,
            provider_attempt_order,
        )
        return None
