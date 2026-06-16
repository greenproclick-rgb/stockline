import feedparser
import requests
import logging

logger = logging.getLogger(__name__)

class AnalysisClient:
    def get_latest_news(self, symbol):
        """Fetches news from Yahoo Finance (More reliable than Seeking Alpha)."""
        # Yahoo Finance RSS is much less likely to block your server
        url = f"https://finance.yahoo.com/rss/headline?s={symbol}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0'
        }
        
        try:
            logger.info(f"Fetching news for {symbol} from Yahoo...")
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code != 200:
                logger.error(f"Yahoo returned status {response.status_code}")
                return "News service is currently responding with an error."

            feed = feedparser.parse(response.content)
            
            if feed.entries:
                # Get the title of the first TWO news stories
                headline1 = feed.entries[0].title
                summary1 = feed.entries[0].summary[:200] # Short snippet
                
                return f"Latest headline: {headline1}. Brief summary: {summary1}"
            
            return f"No recent news articles found for {symbol} on Yahoo Finance."
            
        except Exception as e:
            logger.error(f"RSS Client Error: {e}")
            return "I am unable to reach the news analysis server right now."

    def get_top_gainers(self):
        """Market summary from a stable source."""
        url = "https://www.marketwatch.com/rss/topstories"
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                return "Market mover data is not available."
            
            highlights = "Top market stories right now: "
            for entry in feed.entries[:3]:
                highlights += entry.title + ". "
            return highlights
        except Exception as e:
            return "Unable to retrieve market highlights."
