"""In-memory watchlist and portfolio structures for the MVP."""

from threading import Lock
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class Watchlist:
    owner_id: str
    name: str
    symbols: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=lambda: ["movers", "earnings", "headlines"])
    updated_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PortfolioHolding:
    symbol: str
    shares: float = 0.0
    cost_basis: Optional[float] = None


@dataclass
class Portfolio:
    owner_id: str
    name: str
    holdings: Dict[str, PortfolioHolding] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=lambda: ["rankings", "movers", "earnings"])
    updated_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict:
        data = asdict(self)
        data["holdings"] = [holding for _, holding in sorted(data["holdings"].items())]
        return data


class WatchlistPortfolioStore:
    """Simple in-memory store that can be wired into API or IVR flows."""

    def __init__(self):
        self.watchlists: Dict[tuple[str, str], Watchlist] = {}
        self.portfolios: Dict[tuple[str, str], Portfolio] = {}
        self._lock = Lock()

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return symbol.strip().upper()

    @staticmethod
    def _watchlist_snapshot(owner_id: str, name: str, watchlist: Optional[Watchlist] = None) -> Dict:
        return (watchlist or Watchlist(owner_id=owner_id, name=name)).to_dict()

    @staticmethod
    def _portfolio_snapshot(owner_id: str, name: str, portfolio: Optional[Portfolio] = None) -> Dict:
        return (portfolio or Portfolio(owner_id=owner_id, name=name)).to_dict()

    def add_watchlist_symbol(self, owner_id: str, name: str, symbol: str) -> Dict:
        with self._lock:
            key = (owner_id, name)
            watchlist = self.watchlists.setdefault(key, Watchlist(owner_id=owner_id, name=name))
            normalized = self._normalize_symbol(symbol)
            if normalized not in watchlist.symbols:
                watchlist.symbols.append(normalized)
                watchlist.symbols.sort()
            watchlist.updated_at = _utcnow()
            return watchlist.to_dict()

    def remove_watchlist_symbol(self, owner_id: str, name: str, symbol: str) -> Dict:
        with self._lock:
            key = (owner_id, name)
            watchlist = self.watchlists.get(key)
            if not watchlist:
                return self._watchlist_snapshot(owner_id, name)
            normalized = self._normalize_symbol(symbol)
            watchlist.symbols = [item for item in watchlist.symbols if item != normalized]
            watchlist.updated_at = _utcnow()
            return watchlist.to_dict()

    def get_watchlist(self, owner_id: str, name: str) -> Dict:
        watchlist = self.watchlists.get((owner_id, name))
        return self._watchlist_snapshot(owner_id, name, watchlist)

    def add_portfolio_holding(
        self,
        owner_id: str,
        name: str,
        symbol: str,
        shares: float = 0.0,
        cost_basis: Optional[float] = None,
    ) -> Dict:
        with self._lock:
            key = (owner_id, name)
            portfolio = self.portfolios.setdefault(key, Portfolio(owner_id=owner_id, name=name))
            normalized = self._normalize_symbol(symbol)
            portfolio.holdings[normalized] = PortfolioHolding(
                symbol=normalized,
                shares=float(shares or 0.0),
                cost_basis=float(cost_basis) if cost_basis is not None else None,
            )
            portfolio.updated_at = _utcnow()
            return portfolio.to_dict()

    def remove_portfolio_holding(self, owner_id: str, name: str, symbol: str) -> Dict:
        with self._lock:
            key = (owner_id, name)
            portfolio = self.portfolios.get(key)
            if not portfolio:
                return self._portfolio_snapshot(owner_id, name)
            portfolio.holdings.pop(self._normalize_symbol(symbol), None)
            portfolio.updated_at = _utcnow()
            return portfolio.to_dict()

    def get_portfolio(self, owner_id: str, name: str) -> Dict:
        portfolio = self.portfolios.get((owner_id, name))
        return self._portfolio_snapshot(owner_id, name, portfolio)
