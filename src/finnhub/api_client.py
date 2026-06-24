"""
Finnhub API client for retrieving stock data.
"""

import finnhub
import logging
import concurrent.futures
from typing import Dict, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Curated watchlist used for computing market movers via Finnhub quotes.
_MOVER_WATCHLIST: List[str] = [
    'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
    'TSLA', 'NVDA', 'JPM', 'JNJ', 'V',
    'PG', 'UNH', 'HD', 'MA', 'BAC',
]

class FinnhubClient:
    """Client for interacting with Finnhub API."""
    
    def __init__(self, api_key: str):
        """Initialize Finnhub client.
        
        Args:
            api_key: Finnhub API key
        """
        self.client = finnhub.Client(api_key=api_key)
        self.logger = logger
    
    def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get real-time stock quote.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            
        Returns:
            Dictionary with stock quote data or None if error
        """
        try:
            quote = self.client.quote(symbol)
            return {
                'symbol': symbol,
                'current_price': quote.get('c'),
                'high': quote.get('h'),
                'low': quote.get('l'),
                'open': quote.get('o'),
                'previous_close': quote.get('pc'),
                'change': quote.get('d'),
                'change_pct': quote.get('dp'),
                'timestamp': datetime.fromtimestamp(quote.get('t', 0))
            }
        except Exception as e:
            self.logger.error(f"Error fetching quote for {symbol}: {e}")
            return None
    
    def get_company_profile(self, symbol: str) -> Optional[Dict]:
        """Get company profile information.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary with company information or None if error
        """
        try:
            profile = self.client.company_profile2(symbol=symbol)
            return {
                'symbol': symbol,
                'name': profile.get('name'),
                'industry': profile.get('finnhubIndustry'),
                'country': profile.get('country'),
                'website': profile.get('weburl')
            }
        except Exception as e:
            self.logger.error(f"Error fetching profile for {symbol}: {e}")
            return None
    
    def get_price_target(self, symbol: str) -> Optional[Dict]:
        """Get price target analysis.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary with price target data
        """
        try:
            target = self.client.price_target(symbol=symbol)
            return {
                'symbol': symbol,
                'target_price': target.get('targetPrice'),
                'last_update': target.get('lastUpdated')
            }
        except Exception as e:
            self.logger.error(f"Error fetching price target for {symbol}: {e}")
            return None

    def get_basic_financials(self, symbol: str) -> Optional[Dict]:
        """Get basic financial metrics including P/E ratio and 52-week range.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary with financial metrics or None if error
        """
        try:
            data = self.client.company_basic_financials(symbol, 'all')
            metrics = data.get('metric', {})
            return {
                'symbol': symbol,
                'pe_ratio': metrics.get('peTTM'),
                'week_52_high': metrics.get('52WeekHigh'),
                'week_52_low': metrics.get('52WeekLow'),
                'eps_ttm': metrics.get('epsTTM'),
                'market_cap': metrics.get('marketCapitalization'),
            }
        except Exception as e:
            self.logger.error(f"Error fetching basic financials for {symbol}: {e}")
            return None

    def get_recommendation_trends(self, symbol: str) -> Optional[Dict]:
        """Get analyst recommendation trends.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary with buy/hold/sell counts or None if error
        """
        try:
            trends = self.client.recommendation_trends(symbol)
            if trends and len(trends) > 0:
                latest = trends[0]
                return {
                    'symbol': symbol,
                    'buy': latest.get('buy', 0),
                    'hold': latest.get('hold', 0),
                    'sell': latest.get('sell', 0),
                    'strong_buy': latest.get('strongBuy', 0),
                    'strong_sell': latest.get('strongSell', 0),
                    'period': latest.get('period'),
                }
            return None
        except Exception as e:
            self.logger.error(f"Error fetching recommendation trends for {symbol}: {e}")
            return None

    def get_market_movers(self, category: str = 'gainers') -> Optional[List[Dict]]:
        """Compute top market movers from a curated watchlist using Finnhub quotes.
        
        Args:
            category: 'gainers', 'losers', or 'actives'
            
        Returns:
            List of up to 3 dicts with symbol, price, and change_pct, or None if error
        """
        def _fetch_quote(symbol: str) -> Optional[Dict]:
            try:
                q = self.client.quote(symbol)
                price = q.get('c') or 0
                change_pct = q.get('dp') or 0
                if price > 0:
                    return {'symbol': symbol, 'price': price, 'change_pct': change_pct}
            except Exception:
                pass
            return None

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(_MOVER_WATCHLIST), 10)) as executor:
                results = list(executor.map(_fetch_quote, _MOVER_WATCHLIST))

            stocks = [r for r in results if r is not None]

            if category == 'gainers':
                stocks.sort(key=lambda x: x['change_pct'], reverse=True)
            elif category == 'losers':
                stocks.sort(key=lambda x: x['change_pct'])
            else:  # actives — largest absolute move
                stocks.sort(key=lambda x: abs(x['change_pct']), reverse=True)

            return stocks[:3]
        except Exception as e:
            self.logger.error(f"Error computing market movers ({category}): {e}")
            return None

    def get_market_news(self, category: str = 'general') -> Optional[List[Dict]]:
        """Get general market news headlines.
        
        Args:
            category: Finnhub news category (default 'general')
            
        Returns:
            List of dicts with headline and source, or None if error
        """
        try:
            news = self.client.general_news(category, min_id=0)
            return [
                {'headline': item.get('headline', ''), 'source': item.get('source', '')}
                for item in news[:5]
            ]
        except Exception as e:
            self.logger.error(f"Error fetching market news: {e}")
            return None

    def search_symbol(self, query: str) -> Optional[List[Dict]]:
        """Search for stock symbols.
        
        Args:
            query: Search query (company name or symbol)
            
        Returns:
            List of matching symbols or None if error
        """
        try:
            results = self.client.symbol_lookup(query=query)
            return results.get('result', [])[:5]  # Return top 5 results
        except Exception as e:
            self.logger.error(f"Error searching symbols for '{query}': {e}")
            return None
