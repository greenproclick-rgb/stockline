"""
REST API endpoints for the IVR system.
"""

import logging
from flask import Flask, request, jsonify
from src.finnhub.api_client import FinnhubClient
from src.finnhub.cache import StockCache
from src.finnhub.data_processor import DataProcessor
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
