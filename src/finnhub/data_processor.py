"""
Data processor for formatting stock data for voice presentation.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class DataProcessor:
    """Processes stock data for voice presentation."""

    @staticmethod
    def describe_trend(change_percent: Optional[float], flat_threshold: float = 0.25) -> str:
        """Map a percent move to a simple up/down/flat trend description."""
        if change_percent is None:
            return "flat"
        if change_percent > flat_threshold:
            return "up"
        if change_percent < -flat_threshold:
            return "down"
        return "flat"
    
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
            previous_close = quote.get('previous_close')

            if previous_close in (None, 0):
                return f"{symbol} is trading at ${price:.2f}."

            change = price - previous_close
            change_percent = (change / previous_close) * 100
            trend = DataProcessor.describe_trend(change_percent)
            abs_change = abs(change)
            abs_percent = abs(change_percent)
            
            text = f"{symbol} is trading at ${price:.2f}, "
            if trend == "flat":
                text += f"flat on the day, moving ${abs_change:.2f} or {abs_percent:.2f} percent "
            else:
                text += f"{trend} ${abs_change:.2f} or {abs_percent:.2f} percent on the day "
            text += f"from the previous close of ${previous_close:.2f}. "
            text += f"The short-term trend is {trend}."
            
            return text
        except Exception as e:
            logger.error(f"Error formatting quote: {e}")
            return None

    @staticmethod
    def format_historical_performance(symbol: str, performance: Dict, period_label: str) -> Optional[str]:
        """Format a historical performance snapshot for voice delivery."""
        try:
            if not performance:
                return None

            change = performance.get('change')
            change_percent = performance.get('change_percent')
            trend = DataProcessor.describe_trend(change_percent)

            if change is None and change_percent is None:
                return None

            amount_text = (
                f"{abs(change):.2f} dollars"
                if change is not None
                else None
            )
            percent_text = (
                f"{abs(change_percent):.2f} percent"
                if change_percent is not None
                else None
            )

            if amount_text and percent_text:
                move_text = f"{amount_text}, or {percent_text}"
            else:
                move_text = amount_text or percent_text or "an unavailable amount"

            if trend == "flat":
                return (
                    f"Over the {period_label}, {symbol} has been flat, moving {move_text}. "
                    f"The trend is flat."
                )

            return (
                f"Over the {period_label}, {symbol} is {trend} {move_text}. "
                f"The trend is {trend}."
            )
        except Exception as e:
            logger.error(f"Error formatting historical performance: {e}")
            return None

    @staticmethod
    def format_earnings_for_voice(symbol: str, earnings: Optional[Dict]) -> str:
        """Format earnings timing and summary details for voice delivery."""
        if not earnings:
            return f"Earnings information for {symbol} is not available right now."

        parts = []
        earnings_date = earnings.get('date')
        if earnings_date:
            parts.append(f"The next earnings date for {symbol} is {earnings_date}.")
        else:
            parts.append(f"Earnings timing for {symbol} is not available right now.")

        eps_actual = earnings.get('eps_actual')
        eps_estimate = earnings.get('eps_estimate')
        if eps_actual is not None or eps_estimate is not None:
            summary = "Earnings per share"
            if eps_actual is not None:
                summary += f" came in at {eps_actual:.2f}"
            if eps_estimate is not None:
                summary += f" versus an estimate of {eps_estimate:.2f}"
            parts.append(summary + ".")

        revenue_actual = earnings.get('revenue_actual')
        revenue_estimate = earnings.get('revenue_estimate')
        if revenue_actual is not None or revenue_estimate is not None:
            summary = "Revenue"
            if revenue_actual is not None:
                summary += f" was {revenue_actual:.2f}"
            if revenue_estimate is not None:
                summary += f" against an estimate of {revenue_estimate:.2f}"
            parts.append(summary + ".")

        return " ".join(parts)
    
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
