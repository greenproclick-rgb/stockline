"""
REST API endpoints for the IVR system.
"""

import logging
from flask import Flask, request, jsonify
from src.finnhub.api_client import FinnhubClient
from src.finnhub.cache import StockCache
from src.finnhub.data_processor import DataProcessor
from src.ivr.news_narrator import NewsNarrator
from src.ivr.watchlist_store import WatchlistPortfolioStore
from config.settings import Settings

logger = logging.getLogger(__name__)

class APIEndpoints:
    """Defines REST API endpoints for the IVR system."""
    
    def __init__(self, app: Flask, finnhub_client: FinnhubClient, settings: Settings):
        """Initialize API endpoints.
        
        Args:
            app: Flask application instance
            finnhub_client: Finnhub API client
            settings: Application settings
        """
        self.app = app
        self.finnhub_client = finnhub_client
        self.settings = settings
        self.cache = StockCache()
        self.data_processor = DataProcessor()
        self.watchlist_store = WatchlistPortfolioStore()
        self.setup_routes()

    def _authorize_store_access(self, owner_id: str):
        """Require a simple API token and matching owner header for mutable personal data."""
        token = getattr(self.settings, 'watchlist_api_token', None)
        if not token:
            return jsonify({
                'success': False,
                'error': 'Watchlist API token is not configured'
            }), 403
        if request.headers.get('X-Stockline-Token') != token:
            return jsonify({
                'success': False,
                'error': 'Unauthorized'
            }), 403

        owner_header = request.headers.get('X-Stockline-Owner')
        if not owner_header or owner_header != owner_id:
            return jsonify({
                'success': False,
                'error': 'Owner mismatch'
            }), 403

        return None
    
    def setup_routes(self):
        """Setup all API routes."""
        
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            """Health check endpoint."""
            return jsonify({
                'status': 'healthy',
                'service': 'stockline-ivr',
                'environment': self.settings.environment
            }), 200
        
        @self.app.route('/api/quote/<symbol>', methods=['GET'])
        def get_quote(symbol):
            """Get stock quote for a symbol.
            
            Args:
                symbol: Stock symbol (e.g., AAPL)
                
            Returns:
                JSON response with quote data
            """
            try:
                symbol = symbol.upper()
                
                # Check cache first
                cached_quote = self.cache.get_quote(symbol)
                if cached_quote:
                    logger.info(f"Returning cached quote for {symbol}")
                    return jsonify({
                        'success': True,
                        'data': cached_quote,
                        'cached': True
                    }), 200
                
                # Fetch from Finnhub
                quote = self.finnhub_client.get_quote(symbol)
                
                if quote:
                    # Cache the result
                    self.cache.set_quote(symbol, quote)
                    
                    return jsonify({
                        'success': True,
                        'data': quote,
                        'cached': False
                    }), 200
                else:
                    return jsonify({
                        'success': False,
                        'error': f'Could not find data for symbol {symbol}'
                    }), 404
            
            except Exception as e:
                logger.error(f"Error fetching quote for {symbol}: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/profile/<symbol>', methods=['GET'])
        def get_profile(symbol):
            """Get company profile for a symbol.
            
            Args:
                symbol: Stock symbol
                
            Returns:
                JSON response with company profile
            """
            try:
                symbol = symbol.upper()
                profile = self.finnhub_client.get_company_profile(symbol)
                
                if profile:
                    return jsonify({
                        'success': True,
                        'data': profile
                    }), 200
                else:
                    return jsonify({
                        'success': False,
                        'error': f'Could not find profile for symbol {symbol}'
                    }), 404
            
            except Exception as e:
                logger.error(f"Error fetching profile for {symbol}: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/price-target/<symbol>', methods=['GET'])
        def get_price_target(symbol):
            """Get price target analysis for a symbol.
            
            Args:
                symbol: Stock symbol
                
            Returns:
                JSON response with price target data
            """
            try:
                symbol = symbol.upper()
                target = self.finnhub_client.get_price_target(symbol)
                
                if target:
                    return jsonify({
                        'success': True,
                        'data': target
                    }), 200
                else:
                    return jsonify({
                        'success': False,
                        'error': f'Could not find price target for symbol {symbol}'
                    }), 404
            
            except Exception as e:
                logger.error(f"Error fetching price target for {symbol}: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/search', methods=['GET'])
        def search():
            """Search for stocks by name or symbol.
            
            Query parameters:
                q: Search query (company name or symbol)
                
            Returns:
                JSON response with search results
            """
            try:
                query = request.args.get('q', '').strip()
                
                if not query:
                    return jsonify({
                        'success': False,
                        'error': 'Search query is required'
                    }), 400
                
                results = self.finnhub_client.search_symbol(query)
                
                if results:
                    return jsonify({
                        'success': True,
                        'data': results,
                        'count': len(results)
                    }), 200
                else:
                    return jsonify({
                        'success': False,
                        'error': f'No results found for "{query}"'
                    }), 404
            
            except Exception as e:
                logger.error(f"Error searching for '{query}': {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/quote/<symbol>/voice', methods=['GET'])
        def get_quote_for_voice(symbol):
            """Get stock quote formatted for voice delivery.
            
            Args:
                symbol: Stock symbol
                
            Returns:
                JSON response with voice-formatted quote
            """
            try:
                symbol = symbol.upper()
                quote = self.finnhub_client.get_quote(symbol)
                
                if quote:
                    voice_text = self.data_processor.format_quote_for_voice(quote)
                    
                    return jsonify({
                        'success': True,
                        'symbol': symbol,
                        'voice_text': voice_text,
                        'data': quote
                    }), 200
                else:
                    return jsonify({
                        'success': False,
                        'error': f'Could not find data for symbol {symbol}'
                    }), 404
            
            except Exception as e:
                logger.error(f"Error formatting quote for voice: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/cache/clear', methods=['POST'])
        def clear_cache():
            """Clear the stock data cache.
            
            Returns:
                JSON response indicating success or failure
            """
            try:
                if self.cache.clear_cache():
                    return jsonify({
                        'success': True,
                        'message': 'Cache cleared successfully'
                    }), 200
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Failed to clear cache'
                    }), 500
            
            except Exception as e:
                logger.error(f"Error clearing cache: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/stats', methods=['GET'])
        def get_stats():
            """Get system statistics.
            
            Returns:
                JSON response with system stats
            """
            return jsonify({
                'success': True,
                'environment': self.settings.environment,
                'debug': self.settings.debug,
                'service': 'stockline-ivr',
                'version': '1.0.0'
            }), 200

        @self.app.route('/api/history/<symbol>/voice', methods=['GET'])
        def get_history_for_voice(symbol):
            """Get week, month, and quarter performance formatted for voice."""
            try:
                symbol = symbol.upper()
                performance = self.finnhub_client.get_multi_period_performance(symbol)
                voice_text = self.data_processor.format_historical_overview_for_voice(symbol, performance)
                if not voice_text:
                    return jsonify({
                        'success': False,
                        'error': f'Could not find historical performance for symbol {symbol}'
                    }), 404

                return jsonify({
                    'success': True,
                    'symbol': symbol,
                    'voice_text': voice_text,
                    'data': performance
                }), 200
            except Exception as e:
                logger.error(f"Error formatting historical performance for voice: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Historical performance is currently unavailable'
                }), 500

        @self.app.route('/api/news/<symbol>/voice', methods=['GET'])
        def get_symbol_news_for_voice(symbol):
            """Get stock news headlines plus playback-ready article metadata."""
            try:
                symbol = symbol.upper()
                news = self.finnhub_client.get_company_news(symbol)
                briefing = NewsNarrator.build_briefing(news or [], symbol=symbol)
                if not briefing['headline_count']:
                    return jsonify({
                        'success': False,
                        'error': f'No headlines found for symbol {symbol}'
                    }), 404

                return jsonify({
                    'success': True,
                    'symbol': symbol,
                    'voice_text': " ".join(briefing['headlines']),
                    'data': briefing
                }), 200
            except Exception as e:
                logger.error(f"Error building stock news briefing for {symbol}: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Stock news is currently unavailable'
                }), 500

        @self.app.route('/api/news/market/voice', methods=['GET'])
        def get_market_news_for_voice():
            """Get market-wide headlines plus playback-ready article metadata."""
            try:
                news = self.finnhub_client.get_market_news()
                briefing = NewsNarrator.build_briefing(news or [], symbol='market')
                if not briefing['headline_count']:
                    return jsonify({
                        'success': False,
                        'error': 'No market headlines found'
                    }), 404

                return jsonify({
                    'success': True,
                    'voice_text': " ".join(briefing['headlines']),
                    'data': briefing
                }), 200
            except Exception as e:
                logger.error(f"Error building market news briefing: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Market news is currently unavailable'
                }), 500

        @self.app.route('/api/earnings/<symbol>', methods=['GET'])
        def get_earnings(symbol):
            """Get earnings date and summary when available."""
            try:
                symbol = symbol.upper()
                earnings = self.finnhub_client.get_earnings_summary(symbol)
                if not earnings:
                    return jsonify({
                        'success': False,
                        'error': f'Could not find earnings data for symbol {symbol}'
                    }), 404

                return jsonify({
                    'success': True,
                    'data': earnings,
                    'voice_text': self.data_processor.format_earnings_for_voice(earnings)
                }), 200
            except Exception as e:
                logger.error(f"Error fetching earnings for {symbol}: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Earnings data is currently unavailable'
                }), 500

        @self.app.route('/api/watchlists/<owner_id>/<name>', methods=['GET', 'POST', 'DELETE'])
        def watchlist(owner_id, name):
            """Manage an in-memory watchlist."""
            try:
                auth_error = self._authorize_store_access(owner_id)
                if auth_error:
                    return auth_error
                payload = request.get_json(silent=True) or {}
                symbol = payload.get('symbol') or request.args.get('symbol')

                if request.method == 'POST':
                    if not symbol:
                        return jsonify({'success': False, 'error': 'symbol is required'}), 400
                    data = self.watchlist_store.add_watchlist_symbol(owner_id, name, symbol)
                elif request.method == 'DELETE':
                    if not symbol:
                        return jsonify({'success': False, 'error': 'symbol is required'}), 400
                    data = self.watchlist_store.remove_watchlist_symbol(owner_id, name, symbol)
                else:
                    data = self.watchlist_store.get_watchlist(owner_id, name)

                return jsonify({'success': True, 'data': data}), 200
            except Exception as e:
                logger.error(f"Error managing watchlist {owner_id}/{name}: {e}")
                return jsonify({'success': False, 'error': 'Watchlist service is currently unavailable'}), 500

        @self.app.route('/api/portfolios/<owner_id>/<name>', methods=['GET', 'POST', 'DELETE'])
        def portfolio(owner_id, name):
            """Manage an in-memory portfolio."""
            try:
                auth_error = self._authorize_store_access(owner_id)
                if auth_error:
                    return auth_error
                payload = request.get_json(silent=True) or {}
                symbol = payload.get('symbol') or request.args.get('symbol')

                if request.method == 'POST':
                    if not symbol:
                        return jsonify({'success': False, 'error': 'symbol is required'}), 400
                    data = self.watchlist_store.add_portfolio_holding(
                        owner_id,
                        name,
                        symbol,
                        shares=payload.get('shares', 0.0),
                        cost_basis=payload.get('cost_basis'),
                    )
                elif request.method == 'DELETE':
                    if not symbol:
                        return jsonify({'success': False, 'error': 'symbol is required'}), 400
                    data = self.watchlist_store.remove_portfolio_holding(owner_id, name, symbol)
                else:
                    data = self.watchlist_store.get_portfolio(owner_id, name)

                return jsonify({'success': True, 'data': data}), 200
            except Exception as e:
                logger.error(f"Error managing portfolio {owner_id}/{name}: {e}")
                return jsonify({'success': False, 'error': 'Portfolio service is currently unavailable'}), 500
