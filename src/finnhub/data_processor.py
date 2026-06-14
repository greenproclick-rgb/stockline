"""
Data processor for formatting stock data for voice presentation.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class DataProcessor:
    """Processes stock data for voice presentation."""
    
    @staticmethod
    def format_quote_for_voice(quote: Dict) -> Optional[str]:
        """Format stock quote for voice delivery.
        
        Args:
            quote: Quote dictionary from Finnhub API
            
        Returns:
            Formatted string for voice delivery
        """
        try:
            if not quote:
                return None
            
            symbol = quote.get('symbol', 'Unknown')
            price = quote.get('current_price', 0)
            change = price - quote.get('previous_close', price)
            change_percent = (change / quote.get('previous_close', 1)) * 100
            
            direction = "up" if change >= 0 else "down"
            abs_change = abs(change)
            
            text = f"{symbol} is trading at ${price:.2f}, "
            text += f"{direction} ${abs_change:.2f} or {change_percent:.2f} percent "
            text += f"from the previous close of ${quote.get('previous_close', 0):.2f}."
            
            return text
        except Exception as e:
            logger.error(f"Error formatting quote: {e}")
            return None
    
    @staticmethod
    def format_profile_for_voice(profile: Dict) -> Optional[str]:
        """Format company profile for voice delivery.
        
        Args:
            profile: Profile dictionary from Finnhub API
            
        Returns:
            Formatted string for voice delivery
        """
        try:
            if not profile:
                return None
            
            name = profile.get('name', 'Unknown')
            industry = profile.get('industry', 'Unknown')
            country = profile.get('country', 'Unknown')
            
            text = f"{name} operates in the {industry} industry in {country}."
            return text
        except Exception as e:
            logger.error(f"Error formatting profile: {e}")
            return None
