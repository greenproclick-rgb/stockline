import feedparser
import re

class AnalysisClient:
    def __init__(self):
        # We add a User-Agent so Seeking Alpha doesn't block the request as a bot
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def get_latest_news(self, symbol):
        url = f"https://seekingalpha.com/symbol/{symbol.upper()}/feed"
        
        # Parse the feed
        feed = feedparser.parse(url)
        
        if not feed.entries:
            return f"I'm sorry, I couldn't find any recent analysis for {symbol}."

        # Get the most recent article
        latest_article = feed.entries[0]
        title = latest_article.title
        
        # Clean the HTML out of the summary
        clean_summary = re.sub('<[^<]+?>', '', latest_article.summary)
        
        # Shorten it so the phone call isn't too long
        short_summary = (clean_summary[:350] + '...') if len(clean_summary) > 350 else clean_summary

        return f"Latest headline for {symbol}: {title}. The summary says: {short_summary}"
