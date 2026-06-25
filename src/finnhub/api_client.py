"""
Finnhub API client for retrieving stock data.
"""

import finnhub
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)

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

    def get_basic_financials(self, symbol: str) -> Optional[Dict]:
        """Get basic financial metrics for a symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Dictionary with 52-week range, P/E ratio, beta, etc., or None if error
        """
        try:
            data = self.client.company_basic_financials(symbol, 'all')
            metric = data.get('metric', {})
            return {
                'symbol': symbol,
                '52_week_high': metric.get('52WeekHigh'),
                '52_week_low': metric.get('52WeekLow'),
                'pe_ratio': metric.get('peBasicExclExtraTTM') or metric.get('peTTM'),
                'beta': metric.get('beta'),
                'market_cap': metric.get('marketCapitalization'),
            }
        except Exception as e:
            self.logger.error(f"Error fetching basic financials for {symbol}: {e}")
            return None

    def get_recommendation_trends(self, symbol: str) -> Optional[Dict]:
        """Get analyst recommendation trends for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary with buy/hold/sell counts, or None if error
        """
        try:
            trends = self.client.recommendation_trends(symbol)
            if trends:
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

    def get_company_news(self, symbol: str, days_back: int = 7) -> Optional[List[Dict]]:
        """Get recent company news articles.

        Args:
            symbol: Stock symbol
            days_back: Number of days back to search for news

        Returns:
            List of news items with headline and summary, or None if error
        """
        try:
            to_date = date.today()
            from_date = to_date - timedelta(days=days_back)
            news = self.client.company_news(
                symbol,
                _from=from_date.strftime('%Y-%m-%d'),
                to=to_date.strftime('%Y-%m-%d'),
            )
            return [
                {'headline': item.get('headline', ''), 'summary': item.get('summary', '')}
                for item in (news or [])[:5]
            ]
        except Exception as e:
            self.logger.error(f"Error fetching company news for {symbol}: {e}")
            return None

    def get_market_news(self, category: str = 'general') -> Optional[List[Dict]]:
        """Get general market news headlines.

        Args:
            category: News category (e.g., 'general', 'forex', 'crypto')

        Returns:
            List of news items with headline, or None if error
        """
        try:
            news = self.client.general_news(category, min_id=0)
            return [{'headline': item.get('headline', '')} for item in (news or [])[:5]]
        except Exception as e:
            self.logger.error(f"Error fetching market news: {e}")
            return None

    # Symbols used to compute market movers; covers major large-cap equities.
    _MOVER_SYMBOLS = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN', 'META', 'GOOGL']

    def get_market_movers(self, side: str = 'gainers', count: int = 3) -> Optional[List[Dict]]:
        """Compute market movers from a basket of major symbols.

        Fetches quotes for a predefined set of large-cap symbols, computes
        percentage change versus previous close, and returns the top movers.

        Args:
            side: 'gainers' (highest % gain), 'losers' (biggest % loss),
                  or 'actives' (largest absolute % move)
            count: Maximum number of results to return

        Returns:
            List of dicts with 'symbol', 'pct_change', and 'price', or None if error
        """
        try:
            candidates = []
            for sym in self._MOVER_SYMBOLS:
                quote = self.get_quote(sym)
                if (
                    quote
                    and quote.get('current_price')
                    and quote.get('previous_close')
                    and quote['previous_close'] != 0
                ):
                    pct = (
                        (quote['current_price'] - quote['previous_close'])
                        / quote['previous_close']
                        * 100
                    )
                    candidates.append({
                        'symbol': sym,
                        'pct_change': pct,
                        'price': quote['current_price'],
                    })

            if not candidates:
                return None

            if side == 'gainers':
                candidates.sort(key=lambda x: x['pct_change'], reverse=True)
            elif side == 'losers':
                candidates.sort(key=lambda x: x['pct_change'])
            else:
                candidates.sort(key=lambda x: abs(x['pct_change']), reverse=True)

            return candidates[:count]
        except Exception as e:
            self.logger.error(f"Error computing market movers (side={side}): {e}")
            return None
