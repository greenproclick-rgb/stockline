"""
Main entry point for the Stockline IVR system.
"""

import os
import logging
from dotenv import load_dotenv
from flask import Flask
from src.ivr.call_manager import CallManager
from src.ivr.voice_handler import VoiceHandler
from src.api.endpoints import APIEndpoints
from src.finnhub.api_client import FinnhubClient
from config.settings import Settings

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def initialize_system():
    """Initialize the IVR system components."""
    settings = Settings()
    finnhub_client = FinnhubClient(api_key=os.getenv('FINNHUB_API_KEY'))
    call_manager = CallManager(finnhub_client, settings)
    return call_manager, finnhub_client, settings

def create_app():
    """Create and configure Flask application.
    
    Returns:
        Flask app instance
    """
    app = Flask(__name__)
    
    # Initialize system components
    call_manager, finnhub_client, settings = initialize_system()
    
    # Setup voice handler (Twilio webhooks)
    voice_handler = VoiceHandler(call_manager, settings)
    
    # Merge voice handler routes into main app
    blueprint = getattr(voice_handler.app, 'blueprint', None)
    if blueprint is not None:
        app.register_blueprint(blueprint)
        
    for rule in voice_handler.app.url_map.iter_rules():
        if rule.endpoint != 'static':
            app.add_url_rule(rule.rule, rule.endpoint, voice_handler.app.view_functions[rule.endpoint], methods=rule.methods)
    
    # Setup REST API endpoints
    api_endpoints = APIEndpoints(app, finnhub_client, settings)
    
    # Add error handlers
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return {'error': 'Endpoint not found'}, 404
    
    @app.errorhandler(500)
    def server_error(error):
        """Handle 500 errors."""
        logger.error(f"Server error: {error}")
        return {'error': 'Internal server error'}, 500
    
    return app, settings

def main():
    """Main function to start the IVR system."""
    try:
        logger.info("Initializing Stockline IVR System...")
        
        # Create Flask app
        app, settings = create_app()
        
        logger.info(f"Stockline IVR System started in {settings.environment} mode")
        logger.info("Voice handler listening for Twilio webhooks on /call/incoming")
        logger.info("REST API endpoints available on /api/*")
        
        # Run Flask app
        host = os.getenv('HOST', '0.0.0.0')
        port = int(os.getenv('PORT', 5000))
        debug = settings.debug
        
        app.run(host=host, port=port, debug=debug)
        
    except Exception as e:
        logger.error(f"Error starting IVR system: {e}")
        raise

if __name__ == "__main__":
    main()
