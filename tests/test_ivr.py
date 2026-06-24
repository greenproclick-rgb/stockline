"""
Unit tests for IVR system.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.ivr.call_manager import CallManager
from src.finnhub.api_client import FinnhubClient


class TestCallManager:
    """Tests for CallManager."""
    
    @pytest.fixture
    def mock_finnhub(self):
        """Create mock Finnhub client."""
        return Mock(spec=FinnhubClient)
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        mock = Mock()
        mock.max_retries = 3
        mock.timeout_seconds = 30
        return mock
    
    def test_call_manager_initialization(self, mock_finnhub, mock_settings):
        """Test CallManager initialization."""
        manager = CallManager(mock_finnhub, mock_settings)
        assert manager is not None
        assert manager.finnhub_client == mock_finnhub
    
    def test_handle_incoming_call(self, mock_finnhub, mock_settings):
        """Test handling incoming call."""
        manager = CallManager(mock_finnhub, mock_settings)
        manager.handle_incoming_call('call123', '+1234567890', '+0987654321')
        assert 'call123' in manager.active_calls
    
    def test_end_call(self, mock_finnhub, mock_settings):
        """Test ending a call."""
        manager = CallManager(mock_finnhub, mock_settings)
        manager.handle_incoming_call('call123', '+1234567890', '+0987654321')
        manager._end_call('call123')
        assert 'call123' not in manager.active_calls


class TestVoiceHandler:
    """Tests for VoiceHandler routes."""

    @pytest.fixture
    def mock_finnhub(self):
        return Mock(spec=FinnhubClient)

    @pytest.fixture
    def mock_call_manager(self, mock_finnhub):
        mock = Mock()
        mock.finnhub_client = mock_finnhub
        return mock

    @pytest.fixture
    def mock_settings(self):
        mock = Mock()
        mock.max_retries = 3
        mock.timeout_seconds = 30
        return mock

    @pytest.fixture
    def voice_handler(self, mock_call_manager, mock_settings):
        from src.ivr.voice_handler import VoiceHandler
        return VoiceHandler(mock_call_manager, mock_settings)

    @pytest.fixture
    def client(self, voice_handler):
        voice_handler.app.config['TESTING'] = True
        return voice_handler.app.test_client()

    # ---- get-quote ----

    def test_get_quote_valid_symbol(self, client, mock_finnhub):
        """Quote route speaks the price and offers follow-up options."""
        mock_finnhub.get_quote.return_value = {
            'symbol': 'AAPL',
            'current_price': 175.50,
            'high': 180.0,
            'low': 170.0,
        }
        resp = client.post('/call/get-quote?symbol=AAPL')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert '175.50' in body
        assert 'AAPL' in body
        # Follow-up gather should be present
        assert 'quote-options' in body

    def test_get_quote_no_symbol(self, client, mock_finnhub):
        """Missing symbol redirects to main menu."""
        resp = client.post('/call/get-quote', data={})
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'could not understand' in body.lower() or 'incoming' in body

    def test_get_quote_zero_price(self, client, mock_finnhub):
        """Zero price triggers 'could not find a quote' message."""
        mock_finnhub.get_quote.return_value = {'symbol': 'ZZZZ', 'current_price': 0}
        resp = client.post('/call/get-quote?symbol=ZZZZ')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "couldn't find" in body.lower() or "could not find" in body.lower()

    def test_get_quote_no_finnhub_client(self, mock_call_manager, mock_settings):
        """Missing finnhub client returns config error message."""
        from src.ivr.voice_handler import VoiceHandler
        mock_call_manager.finnhub_client = None
        handler = VoiceHandler(mock_call_manager, mock_settings)
        handler.app.config['TESTING'] = True
        c = handler.app.test_client()
        resp = c.post('/call/get-quote?symbol=AAPL')
        assert resp.status_code == 200
        assert b'configuration error' in resp.data.lower()

    # ---- quote-options ----

    def test_quote_options_digit_1_redirects_to_info(self, client):
        """Pressing 1 after quote redirects to quote-info."""
        resp = client.post('/call/quote-options?symbol=AAPL', data={'Digits': '1'})
        assert resp.status_code == 200
        assert b'quote-info' in resp.data

    def test_quote_options_digit_2_redirects_to_analysis(self, client):
        """Pressing 2 after quote redirects to quote-analysis."""
        resp = client.post('/call/quote-options?symbol=AAPL', data={'Digits': '2'})
        assert resp.status_code == 200
        assert b'quote-analysis' in resp.data

    def test_quote_options_other_digit_redirects_to_menu(self, client):
        """Any other digit returns to main menu."""
        resp = client.post('/call/quote-options?symbol=AAPL', data={'Digits': '*'})
        assert resp.status_code == 200
        assert b'incoming' in resp.data

    # ---- quote-info ----

    def test_quote_info_speaks_financials(self, client, mock_finnhub):
        """quote-info speaks 52-week range, P/E, and analyst price target."""
        mock_finnhub.get_basic_financials.return_value = {
            'symbol': 'AAPL',
            'pe_ratio': 28.5,
            'week_52_high': 200.0,
            'week_52_low': 130.0,
        }
        mock_finnhub.get_price_target.return_value = {
            'symbol': 'AAPL',
            'target_price': 195.0,
        }
        mock_finnhub.get_recommendation_trends.return_value = {
            'symbol': 'AAPL',
            'buy': 20,
            'strong_buy': 10,
            'hold': 5,
            'sell': 1,
            'strong_sell': 0,
        }
        resp = client.get('/call/quote-info?symbol=AAPL')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert '52-week' in body.lower() or '200.00' in body
        assert '28.50' in body or 'earnings' in body.lower()
        assert '195.00' in body or 'target' in body.lower()
        assert 'buy' in body.lower()

    def test_quote_info_no_data(self, client, mock_finnhub):
        """quote-info handles gracefully when all Finnhub calls return None."""
        mock_finnhub.get_basic_financials.return_value = None
        mock_finnhub.get_price_target.return_value = None
        mock_finnhub.get_recommendation_trends.return_value = None
        resp = client.get('/call/quote-info?symbol=AAPL')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'not available' in body.lower()

    # ---- quote-analysis ----

    def test_quote_analysis_speaks_news(self, client):
        """quote-analysis calls AnalysisClient and speaks the result."""
        with patch('src.ivr.voice_handler.AnalysisClient') as MockRSS:
            MockRSS.return_value.get_latest_news.return_value = "Apple beats earnings."
            resp = client.get('/call/quote-analysis?symbol=AAPL')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'Apple beats earnings' in body

    def test_quote_analysis_error_fallback(self, client):
        """quote-analysis handles AnalysisClient exceptions gracefully."""
        with patch('src.ivr.voice_handler.AnalysisClient') as MockRSS:
            MockRSS.return_value.get_latest_news.side_effect = Exception("network error")
            resp = client.get('/call/quote-analysis?symbol=AAPL')
        assert resp.status_code == 200
        assert b'not available' in resp.data.lower()

    # ---- movers-menu ----

    def test_movers_gainers(self, client, mock_finnhub):
        """Pressing 1 speaks top gainers from Finnhub."""
        mock_finnhub.get_market_movers.return_value = [
            {'symbol': 'NVDA', 'price': 500.0, 'change_pct': 5.2},
            {'symbol': 'TSLA', 'price': 250.0, 'change_pct': 4.1},
            {'symbol': 'META', 'price': 300.0, 'change_pct': 3.0},
        ]
        resp = client.post('/call/movers-menu', data={'Digits': '1'})
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'NVDA' in body
        assert 'TSLA' in body
        mock_finnhub.get_market_movers.assert_called_once_with('gainers')

    def test_movers_losers(self, client, mock_finnhub):
        """Pressing 2 speaks top losers."""
        mock_finnhub.get_market_movers.return_value = [
            {'symbol': 'JPM', 'price': 150.0, 'change_pct': -3.5},
        ]
        resp = client.post('/call/movers-menu', data={'Digits': '2'})
        assert resp.status_code == 200
        mock_finnhub.get_market_movers.assert_called_once_with('losers')

    def test_movers_actives(self, client, mock_finnhub):
        """Pressing 3 speaks most active stocks."""
        mock_finnhub.get_market_movers.return_value = [
            {'symbol': 'AAPL', 'price': 175.0, 'change_pct': -2.1},
        ]
        resp = client.post('/call/movers-menu', data={'Digits': '3'})
        assert resp.status_code == 200
        mock_finnhub.get_market_movers.assert_called_once_with('actives')

    def test_movers_no_data(self, client, mock_finnhub):
        """Empty movers list speaks a friendly unavailable message."""
        mock_finnhub.get_market_movers.return_value = []
        resp = client.post('/call/movers-menu', data={'Digits': '1'})
        assert resp.status_code == 200
        assert b'not available' in resp.data.lower()

    def test_movers_exception(self, client, mock_finnhub):
        """Exception in get_market_movers is handled gracefully."""
        mock_finnhub.get_market_movers.side_effect = Exception("API error")
        resp = client.post('/call/movers-menu', data={'Digits': '1'})
        assert resp.status_code == 200
        assert b'unavailable' in resp.data.lower()

    # ---- market-recap ----

    def test_market_recap_finnhub_news(self, client, mock_finnhub):
        """Recap speaks Finnhub news headlines when available."""
        mock_finnhub.get_market_news.return_value = [
            {'headline': 'Fed holds rates steady', 'source': 'Reuters'},
            {'headline': 'S&P 500 hits new high', 'source': 'Bloomberg'},
            {'headline': 'Tech stocks rally', 'source': 'CNBC'},
        ]
        resp = client.post('/call/market-recap')
        assert resp.status_code == 200
        body = resp.data.decode()
        assert 'Fed holds rates steady' in body

    def test_market_recap_rss_fallback(self, client, mock_finnhub):
        """Recap falls back to RSS when Finnhub news returns nothing."""
        mock_finnhub.get_market_news.return_value = []
        with patch('src.ivr.voice_handler.AnalysisClient') as MockRSS:
            MockRSS.return_value.get_market_recap.return_value = "Top market stories right now: Markets up."
            resp = client.post('/call/market-recap')
        assert resp.status_code == 200
        assert b'Markets up' in resp.data

    def test_market_recap_all_fail(self, client, mock_finnhub):
        """Recap speaks unavailable message when all sources fail."""
        mock_finnhub.get_market_news.side_effect = Exception("API error")
        with patch('src.ivr.voice_handler.AnalysisClient') as MockRSS:
            MockRSS.return_value.get_market_recap.side_effect = Exception("RSS error")
            resp = client.post('/call/market-recap')
        assert resp.status_code == 200
        assert b'unavailable' in resp.data.lower()

