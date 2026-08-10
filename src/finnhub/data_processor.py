"""Data processor for formatting stock data for voice presentation."""

import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class DataProcessor:
    """Processes stock data for voice presentation."""

    @staticmethod
    def describe_trend(change_percent: Optional[float]) -> str:
        """Convert a percent move into a short spoken-friendly trend description."""
        if change_percent is None:
            return "The short-term trend is unclear right now."

        abs_change = abs(change_percent)
        if abs_change < 0.25:
            return "The stock is trading mostly flat."
        if change_percent > 0:
            strength = "strong" if abs_change >= 2 else "modest"
            return f"The stock is showing a {strength} upward trend."

        strength = "strong" if abs_change >= 2 else "modest"
        return f"The stock is showing a {strength} downward trend."

    @classmethod
    def format_quote_for_voice(
        cls,
        quote: Dict,
        financials: Optional[Dict] = None,
        price_target: Optional[Dict] = None,
        recommendations: Optional[Dict] = None,
        earnings: Optional[Dict] = None,
        include_extended: bool = False,
    ) -> Optional[str]:
        """Format stock quote for voice delivery."""
        try:
            if not quote:
                return None

            symbol = quote.get('symbol', 'Unknown')
            price = quote.get('current_price')
            if price is None:
                return None

            previous_close = quote.get('previous_close')
            change = None
            change_percent = None

            parts = [f"{symbol} is trading at {price:.2f} dollars."]
            if previous_close not in (None, 0):
                change = price - previous_close
                change_percent = (change / previous_close) * 100
                if abs(change) < 0.005:
                    parts.append("It is unchanged on the day.")
                else:
                    direction = "up" if change > 0 else "down"
                    parts.append(
                        f"It is {direction} {abs(change):.2f} dollars, or {abs(change_percent):.2f} percent, on the day."
                    )

            parts.append(cls.describe_trend(change_percent))

            if not include_extended:
                return " ".join(parts)

            financials = financials or {}
            if financials.get('52_week_low') is not None and financials.get('52_week_high') is not None:
                parts.append(
                    f"The 52-week range is {financials['52_week_low']:.2f} to {financials['52_week_high']:.2f} dollars."
                )
            if financials.get('pe_ratio') is not None:
                parts.append(f"The price to earnings ratio is {financials['pe_ratio']:.2f}.")
            if financials.get('rsi') is not None:
                rsi = financials['rsi']
                if rsi >= 70:
                    rsi_tone = "which suggests the stock may be overbought"
                elif rsi <= 30:
                    rsi_tone = "which suggests the stock may be oversold"
                else:
                    rsi_tone = "which points to a balanced momentum reading"
                parts.append(f"The 14-day RSI is {rsi:.2f}, {rsi_tone}.")

            if recommendations:
                buy = (recommendations.get('buy') or 0) + (recommendations.get('strong_buy') or 0)
                hold = recommendations.get('hold') or 0
                sell = (recommendations.get('sell') or 0) + (recommendations.get('strong_sell') or 0)
                total = buy + hold + sell
                if total:
                    parts.append(f"Analyst ratings are {buy} buy, {hold} hold, and {sell} sell.")

            if price_target and price_target.get('target_price') is not None:
                parts.append(f"The average analyst price target is {price_target['target_price']:.2f} dollars.")

            earnings_text = cls.format_earnings_for_voice(earnings)
            if earnings_text:
                parts.append(earnings_text)

            return " ".join(parts)
        except Exception as e:
            logger.error(f"Error formatting quote: {e}")
            return None

    @classmethod
    def format_historical_change_for_voice(cls, performance: Dict) -> Optional[str]:
        """Format a single historical performance period for voice delivery."""
        try:
            if not performance:
                return None

            symbol = performance.get('symbol', 'Unknown')
            period = performance.get('period', 'period')
            percent_change = performance.get('percent_change')
            absolute_change = performance.get('absolute_change')
            end_price = performance.get('end_price')

            if percent_change is None or absolute_change is None or end_price is None:
                return None

            if abs(percent_change) < 0.25:
                return (
                    f"Over the last {period}, {symbol} was mostly flat and is now at "
                    f"{end_price:.2f} dollars. {cls.describe_trend(percent_change)}"
                )

            direction = "up" if percent_change > 0 else "down"
            return (
                f"Over the last {period}, {symbol} is {direction} {abs(absolute_change):.2f} dollars, "
                f"or {abs(percent_change):.2f} percent, and is now at {end_price:.2f} dollars. "
                f"{cls.describe_trend(percent_change)}"
            )
        except Exception as e:
            logger.error(f"Error formatting historical change: {e}")
            return None

    @classmethod
    def format_historical_overview_for_voice(cls, symbol: str, performance_periods: Dict[str, Dict]) -> Optional[str]:
        """Format week, month, and quarter performance into one spoken summary."""
        try:
            if not performance_periods:
                return None

            ordered_periods = ['week', 'month', 'quarter']
            parts = []
            for period in ordered_periods:
                period_data = performance_periods.get(period)
                if period_data:
                    period_data = dict(period_data)
                    period_data.setdefault('symbol', symbol)
                    period_data.setdefault('period', period)
                    text = cls.format_historical_change_for_voice(period_data)
                    if text:
                        parts.append(text)

            return " ".join(parts) if parts else None
        except Exception as e:
            logger.error(f"Error formatting historical overview: {e}")
            return None

    @staticmethod
    def format_earnings_for_voice(earnings: Optional[Dict]) -> Optional[str]:
        """Format earnings date and summary when available."""
        try:
            if not earnings or not earnings.get('earnings_date'):
                return None

            try:
                earnings_date = datetime.fromisoformat(str(earnings['earnings_date'])).strftime("%B %d, %Y")
            except ValueError:
                earnings_date = str(earnings['earnings_date'])

            parts = [f"The next earnings date is {earnings_date}."]
            if earnings.get('eps_actual') is not None and earnings.get('eps_estimate') is not None:
                parts.append(
                    f"Reported earnings per share were {earnings['eps_actual']:.2f} versus an estimate of "
                    f"{earnings['eps_estimate']:.2f}."
                )
            return " ".join(parts)
        except Exception as e:
            logger.error(f"Error formatting earnings: {e}")
            return None

    @staticmethod
    def format_profile_for_voice(profile: Dict) -> Optional[str]:
        """Format company profile for voice delivery."""
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
