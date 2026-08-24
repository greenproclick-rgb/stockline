"""Helpers for narrating stock news headlines and article drill-down."""

from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Optional


@dataclass
class ArticlePlayback:
    headline: str
    summary: str = ""
    url: Optional[str] = None
    source: Optional[str] = None
    controls: List[str] = field(
        default_factory=lambda: ["play", "pause", "skip", "rewind", "faster", "slower", "next"]
    )

    def to_dict(self) -> Dict:
        return asdict(self)


class NewsNarrator:
    """Transforms headline data into spoken-friendly prompts."""

    @staticmethod
    def build_playlist(articles: Iterable[Dict]) -> List[ArticlePlayback]:
        playlist: List[ArticlePlayback] = []
        for article in articles or []:
            headline = (article or {}).get("headline", "").strip()
            if not headline:
                continue
            playlist.append(
                ArticlePlayback(
                    headline=headline,
                    summary=(article or {}).get("summary", "").strip(),
                    url=(article or {}).get("url"),
                    source=(article or {}).get("source"),
                )
            )
        return playlist

    @staticmethod
    def headline_prompt(article: ArticlePlayback, index: int, total: int, symbol: Optional[str] = None) -> str:
        scope = f" for {symbol}" if symbol else ""
        return f"Headline {index} of {total}{scope}. {article.headline}."

    @staticmethod
    def article_prompt(article: ArticlePlayback) -> str:
        if article.summary:
            return f"{article.headline}. {article.summary}"
        return f"{article.headline}. A full summary is not available yet, but article playback controls are ready for a later update."

    @classmethod
    def build_briefing(cls, articles: Iterable[Dict], symbol: Optional[str] = None, max_items: int = 3) -> Dict:
        playlist = cls.build_playlist(articles)[:max_items]
        return {
            "symbol": symbol,
            "headline_count": len(playlist),
            "headlines": [
                cls.headline_prompt(article, index + 1, len(playlist), symbol=symbol)
                for index, article in enumerate(playlist)
            ],
            "articles": [article.to_dict() for article in playlist],
            "controls": playlist[0].controls if playlist else ArticlePlayback(headline="").controls,
        }
