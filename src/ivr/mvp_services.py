from copy import deepcopy
from typing import Dict, List, Optional

from src.finnhub.data_processor import DataProcessor


class HistoricalPerformanceService:
    """Small service wrapper for historical performance narration."""

    PERIOD_LABELS = {
        'week': 'last week',
        'month': 'last month',
        'quarter': 'last quarter',
    }

    def __init__(self, finnhub_client, data_processor: Optional[DataProcessor] = None):
        self.finnhub_client = finnhub_client
        self.data_processor = data_processor or DataProcessor()

    def get_summary(self, symbol: str, period: str) -> Optional[str]:
        if not self.finnhub_client:
            return None

        period_key = (period or '').lower()
        label = self.PERIOD_LABELS.get(period_key)
        if not label:
            return None

        performance = self.finnhub_client.get_historical_change(symbol, period_key)
        if not performance:
            return None
        return self.data_processor.format_historical_performance(symbol, performance, label)


class NewsService:
    """Unifies stock and market headline access for IVR flows."""

    def __init__(self, finnhub_client):
        self.finnhub_client = finnhub_client

    def get_company_headlines(self, symbol: str) -> List[Dict]:
        if not self.finnhub_client:
            return []
        return self.finnhub_client.get_company_news(symbol) or []

    def get_market_headlines(self) -> List[Dict]:
        if not self.finnhub_client:
            return []
        return self.finnhub_client.get_market_news() or []

    def get_article(self, scope: str, symbol: str = '', index: int = 0) -> Optional[Dict]:
        items = (
            self.get_company_headlines(symbol)
            if scope == 'stock'
            else self.get_market_headlines()
        )
        if index < 0 or index >= len(items):
            return None
        article = deepcopy(items[index])
        article['index'] = index
        article['scope'] = scope
        article['symbol'] = symbol.upper() if symbol else ''
        return article


class InMemoryCollectionStore:
    """In-memory watchlist and portfolio store for MVP use."""

    def __init__(self):
        self._collections = {
            'watchlist': {},
            'portfolio': {},
        }

    def create_collection(self, collection_type: str, name: str) -> Dict:
        collection_key = self._normalize_collection_type(collection_type)
        normalized_name = self._normalize_name(name)
        collection = self._collections[collection_key].setdefault(
            normalized_name,
            {'type': collection_key, 'name': normalized_name, 'symbols': []},
        )
        return deepcopy(collection)

    def add_symbol(self, collection_type: str, name: str, symbol: str) -> Dict:
        collection_key = self._normalize_collection_type(collection_type)
        normalized_name = self._normalize_name(name)
        normalized_symbol = self._normalize_symbol(symbol)
        collection = self._collections[collection_key].setdefault(
            normalized_name,
            {'type': collection_key, 'name': normalized_name, 'symbols': []},
        )
        if normalized_symbol not in collection['symbols']:
            collection['symbols'].append(normalized_symbol)
        return deepcopy(collection)

    def remove_symbol(self, collection_type: str, name: str, symbol: str) -> Dict:
        collection = self._require_collection(collection_type, name)
        normalized_symbol = self._normalize_symbol(symbol)
        collection['symbols'] = [item for item in collection['symbols'] if item != normalized_symbol]
        return deepcopy(collection)

    def get_collection(self, collection_type: str, name: str) -> Optional[Dict]:
        collection_key = self._normalize_collection_type(collection_type)
        normalized_name = self._normalize_name(name)
        collection = self._collections[collection_key].get(normalized_name)
        if not collection:
            return None
        return deepcopy(collection)

    def list_symbols(self, collection_type: str, name: str) -> List[str]:
        collection = self.get_collection(collection_type, name)
        return collection['symbols'] if collection else []

    def _require_collection(self, collection_type: str, name: str) -> Dict:
        collection_key = self._normalize_collection_type(collection_type)
        normalized_name = self._normalize_name(name)
        collection = self._collections[collection_key].get(normalized_name)
        if not collection:
            raise KeyError(f"{collection_key} '{normalized_name}' does not exist")
        return collection

    @staticmethod
    def _normalize_collection_type(collection_type: str) -> str:
        normalized = (collection_type or '').strip().lower()
        if normalized not in {'watchlist', 'portfolio'}:
            raise ValueError("collection_type must be 'watchlist' or 'portfolio'")
        return normalized

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = (name or '').strip()
        if not normalized:
            raise ValueError("name is required")
        return normalized

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = (symbol or '').strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        return normalized
