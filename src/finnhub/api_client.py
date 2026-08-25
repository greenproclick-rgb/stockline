import logging
import requests
from typing import Dict, List, Optional
from datetime import date, timedelta
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
            if side == "gainers":
                endpoint = f"{self.BASE_URL}/stock_market/gainers"
            elif side == "losers":
                endpoint = f"{self.BASE_URL}/stock_market/losers"
            else:  # actives
                endpoint = f"{self.BASE_URL}/stock_market/actives"
            
            params = {"apikey": self.api_key}
            self.logger.info(f"Fetching {side} from FMP API")
            
            response = requests.get(endpoint, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            if not data:
                self.logger.warning(f"No {side} data from FMP")
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
            return movers if movers else None
        
        except requests.exceptions.Timeout:
            self.logger.error(f"FMP API timeout for {side}")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"FMP API error for {side}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error fetching {side}: {e}")
            return None
