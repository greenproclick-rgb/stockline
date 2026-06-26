"""
Unit tests for IVR system.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.ivr.call_manager import CallManager
from src.ivr.voice_handler import VoiceHandler
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_voice_handler(finnhub_client=None):
    """Build a VoiceHandler backed by a mock CallManager."""
    mock_manager = Mock()
    mock_manager.finnhub_client = finnhub_client or Mock(spec=FinnhubClient)
    mock_settings = Mock()
    return VoiceHandler(mock_manager, mock_settings)


# ---------------------------------------------------------------------------
# VoiceHandler — quote flow
# ---------------------------------------------------------------------------

class TestVoiceHandlerQuote:
    """Tests for the /call/get-quote route."""

    def test_get_quote_success(self):
        """Finnhub returns a price; response should include the price and submenu."""
        fh = Mock(spec=FinnhubClient)
        fh.get_quote.return_value = {'symbol': 'AAPL', 'current_price': 175.50, 'previous_close': 172.0}
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/get-quote?symbol=AAPL')
        body = resp.data.decode()

        assert resp.status_code == 200
        assert '175.50' in body
        assert 'AAPL' in body
        # Submenu gather should be present
        assert 'quote-options' in body

    def test_get_quote_no_symbol(self):
        """No digits and no query param; should say it could not understand."""
        vh = _make_voice_handler()
        client = vh.app.test_client()

        resp = client.post('/call/get-quote', data={'Digits': ''})
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'could not understand' in body.lower()

    def test_get_quote_t9_digits(self):
        """T9 digit sequence is decoded to symbol, quote is fetched."""
        fh = Mock(spec=FinnhubClient)
        # '2143' → 'AI' via map_t9_to_symbol
        fh.get_quote.return_value = {'symbol': 'AI', 'current_price': 30.0, 'previous_close': 29.0}
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/get-quote', data={'Digits': '2143'})
        body = resp.data.decode()

        assert resp.status_code == 200
        fh.get_quote.assert_called_once_with('AI')
        assert '30.00' in body

    def test_get_quote_no_price(self):
        """Finnhub returns None price; should say quote not found."""
        fh = Mock(spec=FinnhubClient)
        fh.get_quote.return_value = {'symbol': 'XYZ', 'current_price': None}
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/get-quote?symbol=XYZ')
        body = resp.data.decode()

        assert resp.status_code == 200
        assert "couldn't find" in body.lower() or "could not" in body.lower()

    def test_get_quote_no_client(self):
        """No Finnhub client; should return config error."""
        mock_manager = Mock()
        mock_manager.finnhub_client = None
        vh = VoiceHandler(mock_manager, Mock())
        client = vh.app.test_client()

        resp = client.post('/call/get-quote?symbol=AAPL')
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'configuration error' in body.lower() or 'internal' in body.lower()

    def test_get_quote_exception(self):
        """Finnhub raises exception; should return error message."""
        fh = Mock(spec=FinnhubClient)
        fh.get_quote.side_effect = Exception("Network error")
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/get-quote?symbol=AAPL')
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'error' in body.lower()


# ---------------------------------------------------------------------------
# VoiceHandler — quote submenu
# ---------------------------------------------------------------------------

class TestVoiceHandlerQuoteOptions:
    """Tests for the /call/quote-options route."""

    def test_digit_1_redirects_to_stock_info(self):
        """Pressing 1 should redirect to /call/stock-info."""
        vh = _make_voice_handler()
        client = vh.app.test_client()

        resp = client.post('/call/quote-options?symbol=AAPL', data={'Digits': '1'})
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'stock-info' in body
        assert 'AAPL' in body

    def test_digit_2_redirects_to_stock_analysis(self):
        """Pressing 2 should redirect to /call/stock-analysis."""
        vh = _make_voice_handler()
        client = vh.app.test_client()

        resp = client.post('/call/quote-options?symbol=MSFT', data={'Digits': '2'})
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'stock-analysis' in body
        assert 'MSFT' in body

    def test_star_redirects_to_incoming(self):
        """Pressing * (or any other digit) should redirect to /call/incoming."""
        vh = _make_voice_handler()
        client = vh.app.test_client()

        resp = client.post('/call/quote-options?symbol=AAPL', data={'Digits': '*'})
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'incoming' in body


# ---------------------------------------------------------------------------
# VoiceHandler — full stock info
# ---------------------------------------------------------------------------

class TestVoiceHandlerStockInfo:
    """Tests for the /call/stock-info route."""

    def test_stock_info_full_data(self):
        """All Finnhub calls succeed; response should include all data points."""
        fh = Mock(spec=FinnhubClient)
        fh.get_quote.return_value = {
            'symbol': 'AAPL',
            'current_price': 180.0,
            'high': 185.0,
            'low': 178.0,
            'previous_close': 175.0,
        }
        fh.get_basic_financials.return_value = {
            'symbol': 'AAPL',
            '52_week_high': 200.0,
            '52_week_low': 130.0,
            'pe_ratio': 28.5,
            'beta': 1.2,
        }
        fh.get_price_target.return_value = {'symbol': 'AAPL', 'target_price': 210.0}
        fh.get_recommendation_trends.return_value = {
            'symbol': 'AAPL',
            'buy': 15,
            'strong_buy': 10,
            'hold': 5,
            'sell': 2,
            'strong_sell': 1,
        }
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/stock-info?symbol=AAPL')
        body = resp.data.decode()

        assert resp.status_code == 200
        assert '180.00' in body            # current price
        assert '52' in body                # 52-week range mentioned
        assert '200.00' in body            # 52-week high
        assert '130.00' in body            # 52-week low
        assert '28.50' in body             # P/E ratio
        assert '210.00' in body            # price target
        assert '25' in body or 'buy' in body.lower()  # buy count (15+10=25)

    def test_stock_info_no_data(self):
        """Finnhub returns nothing; should say could not retrieve info."""
        fh = Mock(spec=FinnhubClient)
        fh.get_quote.return_value = None
        fh.get_basic_financials.return_value = None
        fh.get_price_target.return_value = None
        fh.get_recommendation_trends.return_value = None
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/stock-info?symbol=XYZ')
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'could not retrieve' in body.lower()

    def test_stock_info_no_symbol(self):
        """Empty symbol; should say could not retrieve."""
        vh = _make_voice_handler()
        client = vh.app.test_client()

        resp = client.post('/call/stock-info')
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'could not retrieve' in body.lower() or 'sorry' in body.lower()


# ---------------------------------------------------------------------------
# VoiceHandler — stock analysis
# ---------------------------------------------------------------------------

class TestVoiceHandlerStockAnalysis:
    """Tests for the /call/stock-analysis route."""

    def test_stock_analysis_success(self):
        """Company news returned; response should include headlines."""
        fh = Mock(spec=FinnhubClient)
        fh.get_company_news.return_value = [
            {'headline': 'Apple hits all-time high', 'summary': ''},
            {'headline': 'iPhone sales surge in Asia', 'summary': ''},
        ]
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/stock-analysis?symbol=AAPL')
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'AAPL' in body
        assert 'Apple hits all-time high' in body

    def test_stock_analysis_no_news(self):
        """No news found; should say no recent analysis."""
        fh = Mock(spec=FinnhubClient)
        fh.get_company_news.return_value = []
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/stock-analysis?symbol=AAPL')
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'no recent' in body.lower() or 'not found' in body.lower()

    def test_stock_analysis_no_symbol(self):
        """Empty symbol; should say sorry."""
        vh = _make_voice_handler()
        client = vh.app.test_client()

        resp = client.post('/call/stock-analysis')
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'sorry' in body.lower() or 'could not' in body.lower()


# ---------------------------------------------------------------------------
# VoiceHandler — market movers
# ---------------------------------------------------------------------------

class TestVoiceHandlerMovers:
    """Tests for the /call/movers-menu route."""

    def _mover_data(self):
        return [
            {'symbol': 'NVDA', 'pct_change': 4.5, 'price': 500.0},
            {'symbol': 'TSLA', 'pct_change': 3.1, 'price': 200.0},
            {'symbol': 'AAPL', 'pct_change': 1.2, 'price': 180.0},
        ]

    def test_movers_gainers(self):
        """Digit 1 → gainers; response should list symbols going up."""
        fh = Mock(spec=FinnhubClient)
        fh.get_market_movers.return_value = self._mover_data()
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/movers-menu', data={'Digits': '1'})
        body = resp.data.decode()

        assert resp.status_code == 200
        fh.get_market_movers.assert_called_once_with('gainers')
        assert 'NVDA' in body
        assert 'gainers' in body.lower()

    def test_movers_losers(self):
        """Digit 2 → losers; response should list symbols going down."""
        fh = Mock(spec=FinnhubClient)
        fh.get_market_movers.return_value = [
            {'symbol': 'META', 'pct_change': -3.0, 'price': 300.0},
        ]
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/movers-menu', data={'Digits': '2'})
        body = resp.data.decode()

        assert resp.status_code == 200
        fh.get_market_movers.assert_called_once_with('losers')
        assert 'META' in body
        assert 'down' in body.lower()

    def test_movers_actives(self):
        """Digit 3 → actives."""
        fh = Mock(spec=FinnhubClient)
        fh.get_market_movers.return_value = self._mover_data()
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/movers-menu', data={'Digits': '3'})
        body = resp.data.decode()

        assert resp.status_code == 200
        fh.get_market_movers.assert_called_once_with('actives')

    def test_movers_no_data(self):
        """Finnhub returns None; should say unavailable."""
        fh = Mock(spec=FinnhubClient)
        fh.get_market_movers.return_value = None
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/movers-menu', data={'Digits': '1'})
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'unavailable' in body.lower()

    def test_movers_no_client(self):
        """No Finnhub client; should say unavailable."""
        mock_manager = Mock()
        mock_manager.finnhub_client = None
        vh = VoiceHandler(mock_manager, Mock())
        client = vh.app.test_client()

        resp = client.post('/call/movers-menu', data={'Digits': '1'})
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'unavailable' in body.lower()


# ---------------------------------------------------------------------------
# VoiceHandler — market recap
# ---------------------------------------------------------------------------

class TestVoiceHandlerMarketRecap:
    """Tests for the /call/market-recap route."""

    def test_market_recap_success(self):
        """Finnhub returns a spoken summary; response should include recap details."""
        fh = Mock(spec=FinnhubClient)
        fh.get_market_summary.return_value = [
            'Stocks are trading higher today.',
            'The S and P 500 is up 1.10 percent.',
            'Top story: Fed holds rates steady.',
        ]
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/market-recap')
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'Stocks are trading higher today.' in body
        assert 'Fed holds rates steady' in body
        assert 'recap' in body.lower()

    def test_market_recap_no_summary(self):
        """No summary returned; should say unavailable."""
        fh = Mock(spec=FinnhubClient)
        fh.get_market_summary.return_value = []
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/market-recap')
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'unavailable' in body.lower()

    def test_market_recap_no_client(self):
        """No Finnhub client; should say unavailable."""
        mock_manager = Mock()
        mock_manager.finnhub_client = None
        vh = VoiceHandler(mock_manager, Mock())
        client = vh.app.test_client()

        resp = client.post('/call/market-recap')
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'unavailable' in body.lower()

    def test_market_recap_exception(self):
        """Finnhub raises exception; should return error message."""
        fh = Mock(spec=FinnhubClient)
        fh.get_market_summary.side_effect = Exception("timeout")
        vh = _make_voice_handler(fh)
        client = vh.app.test_client()

        resp = client.post('/call/market-recap')
        body = resp.data.decode()

        assert resp.status_code == 200
        assert 'unavailable' in body.lower()


# ---------------------------------------------------------------------------
# FinnhubClient — new methods
# ---------------------------------------------------------------------------

class TestFinnhubClientMethods:
    """Tests for the new FinnhubClient methods."""

    @pytest.fixture
    def mock_raw_client(self):
        """A mock for the underlying finnhub.Client."""
        return Mock()

    @pytest.fixture
    def fh_client(self, mock_raw_client):
        """FinnhubClient with its internal client replaced by a mock."""
        client = FinnhubClient.__new__(FinnhubClient)
        client.client = mock_raw_client
        client.logger = Mock()
        return client

    # get_basic_financials
    def test_get_basic_financials_success(self, fh_client, mock_raw_client):
        mock_raw_client.company_basic_financials.return_value = {
            'metric': {
                '52WeekHigh': 220.0,
                '52WeekLow': 120.0,
                'peBasicExclExtraTTM': 25.0,
                'beta': 1.1,
                'marketCapitalization': 3000000,
            }
        }
        result = fh_client.get_basic_financials('AAPL')
        assert result['52_week_high'] == 220.0
        assert result['52_week_low'] == 120.0
        assert result['pe_ratio'] == 25.0
        assert result['beta'] == 1.1

    def test_get_basic_financials_error(self, fh_client, mock_raw_client):
        mock_raw_client.company_basic_financials.side_effect = Exception("API error")
        result = fh_client.get_basic_financials('AAPL')
        assert result is None

    # get_recommendation_trends
    def test_get_recommendation_trends_success(self, fh_client, mock_raw_client):
        mock_raw_client.recommendation_trends.return_value = [
            {'buy': 20, 'hold': 8, 'sell': 3, 'strongBuy': 5, 'strongSell': 1, 'period': '2024-01-01'}
        ]
        result = fh_client.get_recommendation_trends('AAPL')
        assert result['buy'] == 20
        assert result['hold'] == 8
        assert result['sell'] == 3
        assert result['strong_buy'] == 5
        assert result['period'] == '2024-01-01'

    def test_get_recommendation_trends_empty(self, fh_client, mock_raw_client):
        mock_raw_client.recommendation_trends.return_value = []
        result = fh_client.get_recommendation_trends('AAPL')
        assert result is None

    def test_get_recommendation_trends_error(self, fh_client, mock_raw_client):
        mock_raw_client.recommendation_trends.side_effect = Exception("error")
        result = fh_client.get_recommendation_trends('AAPL')
        assert result is None

    # get_company_news
    def test_get_company_news_success(self, fh_client, mock_raw_client):
        mock_raw_client.company_news.return_value = [
            {'headline': 'Good news', 'summary': 'Summary here'},
            {'headline': 'More news', 'summary': ''},
        ]
        result = fh_client.get_company_news('AAPL')
        assert len(result) == 2
        assert result[0]['headline'] == 'Good news'

    def test_get_company_news_empty(self, fh_client, mock_raw_client):
        mock_raw_client.company_news.return_value = []
        result = fh_client.get_company_news('AAPL')
        assert result == []

    def test_get_company_news_error(self, fh_client, mock_raw_client):
        mock_raw_client.company_news.side_effect = Exception("error")
        result = fh_client.get_company_news('AAPL')
        assert result is None

    # get_market_news
    def test_get_market_news_success(self, fh_client, mock_raw_client):
        mock_raw_client.general_news.return_value = [
            {'headline': 'Market rallies'},
            {'headline': 'Tech sector leads gains'},
        ]
        result = fh_client.get_market_news()
        assert len(result) == 2
        assert result[0]['headline'] == 'Market rallies'
        mock_raw_client.general_news.assert_called_once_with('general', min_id=0)

    def test_get_market_news_error(self, fh_client, mock_raw_client):
        mock_raw_client.general_news.side_effect = Exception("error")
        result = fh_client.get_market_news()
        assert result is None

    # get_market_movers
    def test_get_market_movers_gainers(self, fh_client):
        """Movers should sort by descending pct_change for 'gainers'."""
        quote_data = {
            'AAPL': {'current_price': 182.0, 'previous_close': 180.0},  # +1.11%
            'NVDA': {'current_price': 510.0, 'previous_close': 490.0},  # +4.08%
            'TSLA': {'current_price': 195.0, 'previous_close': 200.0},  # -2.50%
        }

        def fake_get_quote(sym):
            d = quote_data.get(sym)
            if d:
                return {'symbol': sym, 'current_price': d['current_price'], 'previous_close': d['previous_close']}
            return None

        fh_client.get_quote = fake_get_quote
        fh_client._get_sp500_symbols = Mock(return_value=list(quote_data.keys()))

        result = fh_client.get_market_movers('gainers', count=3)

        assert result is not None
        assert result[0]['symbol'] == 'NVDA'   # highest gainer
        assert result[1]['symbol'] == 'AAPL'
        assert result[2]['symbol'] == 'TSLA'   # only loser, still included

    def test_get_market_movers_losers(self, fh_client):
        """Losers should sort by ascending pct_change."""
        quote_data = {
            'AAPL': {'current_price': 182.0, 'previous_close': 180.0},  # +1.11%
            'META': {'current_price': 290.0, 'previous_close': 300.0},  # -3.33%
        }

        def fake_get_quote(sym):
            d = quote_data.get(sym)
            if d:
                return {'symbol': sym, 'current_price': d['current_price'], 'previous_close': d['previous_close']}
            return None

        fh_client.get_quote = fake_get_quote
        fh_client._get_sp500_symbols = Mock(return_value=list(quote_data.keys()))

        result = fh_client.get_market_movers('losers', count=2)

        assert result[0]['symbol'] == 'META'   # biggest loser first

    def test_get_market_movers_no_quotes(self, fh_client):
        """All get_quote calls return None; result should be None."""
        fh_client.get_quote = Mock(return_value=None)
        fh_client._get_sp500_symbols = Mock(return_value=['AAPL'])

        result = fh_client.get_market_movers('gainers')

        assert result is None

    def test_get_sp500_symbols_success(self, fh_client, mock_raw_client):
        mock_raw_client.indices_const.return_value = {
            'constituents': [{'symbol': 'AAPL'}, {'symbol': 'MSFT'}, 'NVDA']
        }

        result = fh_client._get_sp500_symbols()

        assert result == ['AAPL', 'MSFT', 'NVDA']
        mock_raw_client.indices_const.assert_called_once_with(symbol='^GSPC')

    def test_get_market_summary_success(self, fh_client):
        quote_data = {
            'SPY': {'current_price': 510.0, 'previous_close': 500.0},
            'QQQ': {'current_price': 440.0, 'previous_close': 445.0},
            'DIA': {'current_price': 390.0, 'previous_close': 388.0},
        }

        def fake_get_quote(sym):
            data = quote_data.get(sym)
            return {'symbol': sym, **data} if data else None

        fh_client.get_quote = fake_get_quote
        fh_client.get_market_news = Mock(return_value=[{'headline': 'Fed holds rates steady'}])

        result = fh_client.get_market_summary()

        assert result is not None
        assert 'today' in result[0].lower()
        assert any('S and P 500' in line for line in result)
        assert any('Fed holds rates steady' in line for line in result)
