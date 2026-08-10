"""Focused tests for the stock voice MVP additions."""

from unittest.mock import Mock

from flask import Flask

from src.api.endpoints import APIEndpoints
from src.finnhub.api_client import FinnhubClient
from src.finnhub.data_processor import DataProcessor
from src.ivr.news_narrator import NewsNarrator
from src.ivr.voice_handler import VoiceHandler
from src.ivr.watchlist_store import WatchlistPortfolioStore


def _make_voice_handler(finnhub_client=None):
    manager = Mock()
    manager.finnhub_client = finnhub_client or Mock(spec=FinnhubClient)
    return VoiceHandler(manager, Mock())


def _make_api_client(finnhub_client=None):
    app = Flask(__name__)
    settings = Mock()
    settings.environment = "test"
    settings.debug = False
    APIEndpoints(app, finnhub_client or Mock(spec=FinnhubClient), settings)
    return app.test_client()


class TestDataProcessorMvp:
    def test_format_quote_for_voice_with_extended_fields(self):
        text = DataProcessor.format_quote_for_voice(
            {
                "symbol": "AAPL",
                "current_price": 180.0,
                "previous_close": 175.0,
            },
            financials={"52_week_low": 130.0, "52_week_high": 200.0, "pe_ratio": 28.5, "rsi": 72.0},
            price_target={"target_price": 210.0},
            recommendations={"buy": 15, "strong_buy": 10, "hold": 5, "sell": 2, "strong_sell": 1},
            earnings={"earnings_date": "2026-08-25", "eps_actual": 2.0, "eps_estimate": 1.8},
            include_extended=True,
        )

        assert "180.00 dollars" in text
        assert "2.86 percent" in text
        assert "upward trend" in text
        assert "52-week range" in text
        assert "28.50" in text
        assert "RSI" in text
        assert "25 buy" in text
        assert "210.00 dollars" in text
        assert "August 25, 2026" in text

    def test_format_historical_overview_for_voice(self):
        text = DataProcessor.format_historical_overview_for_voice(
            "MSFT",
            {
                "week": {"period": "week", "absolute_change": 5.0, "percent_change": 2.5, "end_price": 420.0},
                "month": {"period": "month", "absolute_change": -3.0, "percent_change": -0.7, "end_price": 420.0},
                "quarter": {"period": "quarter", "absolute_change": 0.1, "percent_change": 0.02, "end_price": 420.0},
            },
        )

        assert "last week" in text
        assert "last month" in text
        assert "last quarter" in text
        assert "up 5.00 dollars" in text
        assert "mostly flat" in text


class TestNewsNarratorMvp:
    def test_build_briefing_exposes_article_controls(self):
        briefing = NewsNarrator.build_briefing(
            [{"headline": "Apple launches AI push", "summary": "Management highlighted new AI products.", "url": "https://example.com"}],
            symbol="AAPL",
        )

        assert briefing["headline_count"] == 1
        assert "Headline 1 of 1 for AAPL" in briefing["headlines"][0]
        assert "pause" in briefing["controls"]
        assert briefing["articles"][0]["summary"] == "Management highlighted new AI products."


class TestWatchlistPortfolioStore:
    def test_watchlist_add_remove_and_capabilities(self):
        store = WatchlistPortfolioStore()
        state = store.add_watchlist_symbol("caller-1", "favorites", "aapl")
        state = store.add_watchlist_symbol("caller-1", "favorites", "msft")
        state = store.remove_watchlist_symbol("caller-1", "favorites", "aapl")

        assert state["symbols"] == ["MSFT"]
        assert "movers" in state["capabilities"]
        assert "earnings" in state["capabilities"]

    def test_portfolio_add_and_list_holdings(self):
        store = WatchlistPortfolioStore()
        store.add_portfolio_holding("caller-1", "core", "nvda", shares=3, cost_basis=100.5)
        state = store.get_portfolio("caller-1", "core")

        assert state["holdings"][0]["symbol"] == "NVDA"
        assert state["holdings"][0]["shares"] == 3.0
        assert "rankings" in state["capabilities"]


class TestVoiceHandlerMvp:
    def test_get_quote_adds_voice_friendly_day_change_summary(self):
        fh = Mock(spec=FinnhubClient)
        fh.get_quote.return_value = {"symbol": "AAPL", "current_price": 175.5, "previous_close": 172.0}
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post("/call/get-quote?symbol=AAPL")
        body = resp.data.decode()

        assert resp.status_code == 200
        assert "2.03 percent" in body
        assert "upward trend" in body

    def test_historical_performance_route_reads_week_month_and_quarter(self):
        fh = Mock(spec=FinnhubClient)
        fh.get_multi_period_performance.return_value = {
            "week": {"symbol": "AAPL", "period": "week", "absolute_change": 5.0, "percent_change": 2.5, "end_price": 180.0},
            "month": {"symbol": "AAPL", "period": "month", "absolute_change": 10.0, "percent_change": 6.0, "end_price": 180.0},
            "quarter": {"symbol": "AAPL", "period": "quarter", "absolute_change": -2.0, "percent_change": -1.0, "end_price": 180.0},
        }
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post("/call/historical-performance?symbol=AAPL")
        body = resp.data.decode()

        assert resp.status_code == 200
        assert "last week" in body
        assert "last month" in body
        assert "last quarter" in body


class TestApiEndpointsMvp:
    def test_history_voice_endpoint_returns_voice_text(self):
        fh = Mock(spec=FinnhubClient)
        fh.get_multi_period_performance.return_value = {
            "week": {"symbol": "AAPL", "period": "week", "absolute_change": 1.0, "percent_change": 1.0, "end_price": 101.0},
            "month": {"symbol": "AAPL", "period": "month", "absolute_change": 2.0, "percent_change": 2.0, "end_price": 102.0},
            "quarter": {"symbol": "AAPL", "period": "quarter", "absolute_change": 3.0, "percent_change": 3.0, "end_price": 103.0},
        }
        client = _make_api_client(fh)

        resp = client.get("/api/history/AAPL/voice")
        payload = resp.get_json()

        assert resp.status_code == 200
        assert payload["success"] is True
        assert "last week" in payload["voice_text"]

    def test_watchlist_endpoint_adds_and_lists_symbols(self):
        client = _make_api_client()

        add_resp = client.post("/api/watchlists/caller-1/favorites", json={"symbol": "tsla"})
        list_resp = client.get("/api/watchlists/caller-1/favorites")

        assert add_resp.status_code == 200
        assert list_resp.status_code == 200
        assert list_resp.get_json()["data"]["symbols"] == ["TSLA"]
