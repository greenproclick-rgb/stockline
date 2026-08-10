"""
REST API endpoints for the IVR system.
"""

import logging
from flask import Flask, request, jsonify
from src.finnhub.api_client import FinnhubClient
from src.finnhub.cache import StockCache
from src.finnhub.data_processor import DataProcessor
from src.ivr.mvp_services import HistoricalPerformanceService, InMemoryCollectionStore, NewsService
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
        self.history_service = HistoricalPerformanceService(finnhub_client, self.data_processor)
        self.news_service = NewsService(finnhub_client)
        self.collection_store = InMemoryCollectionStore()
        self.setup_routes()
    
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

        @self.app.route('/api/history/<symbol>/<period>', methods=['GET'])
        def get_historical_voice_summary(symbol, period):
            """Get a historical performance narration for voice delivery."""
            try:
                summary = self.history_service.get_summary(symbol.upper(), period)
                if summary:
                    return jsonify({
                        'success': True,
                        'symbol': symbol.upper(),
                        'period': period,
                        'voice_text': summary,
                    }), 200
                return jsonify({
                    'success': False,
                    'error': f'Historical performance for {symbol.upper()} is unavailable'
                }), 404
            except Exception as e:
                logger.error(f"Error fetching historical summary for {symbol}: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Historical performance service is currently unavailable'
                }), 500

        @self.app.route('/api/news/<symbol>', methods=['GET'])
        def get_stock_news(symbol):
            """Get a small set of company headlines for a symbol."""
            try:
                headlines = self.news_service.get_company_headlines(symbol.upper())
                return jsonify({
                    'success': True,
                    'symbol': symbol.upper(),
                    'headlines': headlines,
                    'count': len(headlines),
                }), 200
            except Exception as e:
                logger.error(f"Error fetching stock news for {symbol}: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Stock news is currently unavailable'
                }), 500

        @self.app.route('/api/news/market', methods=['GET'])
        def get_market_news():
            """Get market-wide headlines."""
            try:
                headlines = self.news_service.get_market_headlines()
                return jsonify({
                    'success': True,
                    'headlines': headlines,
                    'count': len(headlines),
                }), 200
            except Exception as e:
                logger.error(f"Error fetching market news: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Market news is currently unavailable'
                }), 500

        @self.app.route('/api/news/article', methods=['GET'])
        def get_article_foundation():
            """Expose a placeholder article playback contract for future IVR controls."""
            scope = request.args.get('scope', 'stock')
            symbol = request.args.get('symbol', '').upper()
            try:
                index = int(request.args.get('index', 0))
            except (TypeError, ValueError):
                return jsonify({
                    'success': False,
                    'error': 'index must be an integer'
                }), 400
            article = self.news_service.get_article(scope, symbol=symbol, index=index)
            if article:
                return jsonify({
                    'success': True,
                    'article': article,
                    'playback_controls': ['play', 'pause', 'skip', 'rewind', 'speed'],
                }), 200
            return jsonify({
                'success': False,
                'error': 'Article is unavailable'
            }), 404

        @self.app.route('/api/earnings/<symbol>', methods=['GET'])
        def get_earnings(symbol):
            """Get the next earnings date and a minimal earnings summary."""
            try:
                earnings = self.finnhub_client.get_earnings(symbol.upper())
                if earnings:
                    return jsonify({
                        'success': True,
                        'symbol': symbol.upper(),
                        'data': earnings,
                        'voice_text': self.data_processor.format_earnings_for_voice(symbol.upper(), earnings),
                    }), 200
                return jsonify({
                    'success': False,
                    'error': f'Earnings information for {symbol.upper()} is unavailable'
                }), 404
            except Exception as e:
                logger.error(f"Error fetching earnings for {symbol}: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Earnings information is currently unavailable'
                }), 500

        @self.app.route('/api/collections/<collection_type>/<name>', methods=['POST', 'GET'])
        def collection_detail(collection_type, name):
            """Create or fetch a watchlist or portfolio."""
            try:
                if request.method == 'POST':
                    data = self.collection_store.create_collection(collection_type, name)
                    return jsonify({'success': True, 'data': data}), 201

                data = self.collection_store.get_collection(collection_type, name)
                if data:
                    return jsonify({'success': True, 'data': data}), 200
                return jsonify({
                    'success': False,
                    'error': f'{collection_type} {name} was not found'
                }), 404
            except (ValueError, KeyError):
                return jsonify({'success': False, 'error': 'Invalid collection request'}), 400

        @self.app.route('/api/collections/<collection_type>/<name>/symbols', methods=['POST'])
        def add_collection_symbol(collection_type, name):
            """Add a symbol to a watchlist or portfolio."""
            try:
                payload = request.get_json(silent=True) or {}
                symbol = payload.get('symbol')
                data = self.collection_store.add_symbol(collection_type, name, symbol)
                return jsonify({'success': True, 'data': data}), 200
            except (ValueError, KeyError):
                return jsonify({'success': False, 'error': 'Invalid collection request'}), 400

        @self.app.route('/api/collections/<collection_type>/<name>/symbols/<symbol>', methods=['DELETE'])
        def remove_collection_symbol(collection_type, name, symbol):
            """Remove a symbol from a watchlist or portfolio."""
            try:
                data = self.collection_store.remove_symbol(collection_type, name, symbol)
                return jsonify({'success': True, 'data': data}), 200
            except (ValueError, KeyError):
                return jsonify({'success': False, 'error': 'Invalid collection request'}), 400
        
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
