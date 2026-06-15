import feedparser
import re

class RSSClient:
    def get_analysis(self, symbol):
        # Seeking Alpha RSS URL
        url = f"https://seekingalpha.com/symbol/{symbol.upper()}/feed"
        feed = feedparser.parse(url)
        
        if not feed.entries:
            return f"No recent analysis found for {symbol}."
            
        # Get latest entry and clean HTML tags
        latest = feed.entries[0]
        summary_clean = re.sub('<[^<]+?>', '', latest.summary)
        
        return {
            'title': latest.title,
            'summary': summary_clean[:400] # Limit length for voice
        }
