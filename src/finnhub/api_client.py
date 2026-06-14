"""
Finnhub API client for retrieving stock data.
"""

import finnhub
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta

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
