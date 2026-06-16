import feedparser
import requests
import logging

logger = logging.getLogger(__name__)

class AnalysisClient:
    """Fetches financial analysis and market news."""

    def get_latest_news(self, symbol):
        """Fetches latest analysis from Seeking Alpha RSS."""
        url = f"https://seekingalpha.com/api/v3/symbols/{symbol}/rss.xml"
        
        # This header is CRITICAL. Without it, SeekingAlpha blocks you.
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            # We use requests first so we can add the headers
            response = requests.get(url, headers=headers, timeout=10)
            feed = feedparser.parse(response.content)
            
            if feed.entries:
                # We get the 'summary' from the first news item
                text = feed.entries[0].summary
                # Shorten it so the IVR doesn't talk for 20 minutes
                return text[:600] + "... End of analysis." 
            
            return f"I found the price for {symbol}, but no recent analysis articles are available."
            
        except Exception as e:
            logger.error(f"Error fetching RSS for {symbol}: {e}")
            return "Analysis data is currently unreachable."

    def get_top_gainers(self):
        """Fetches major market highlights for Menu Option 3."""
        # This is a general market overview feed
        url = "https://www.investing.com/rss/market_overview.rss"
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                return "I'm sorry, major gainer data is not available right now."
            
            # Combine the first 3 headlines
            highlights = "Today's market highlights: "
            for entry in feed.entries[:3]:
                highlights += entry.title + ". "
            
            return highlights
        except Exception as e:
            logger.error(f"Error fetching market summary: {e}")
            return "I am currently unable to retrieve market overview data."
