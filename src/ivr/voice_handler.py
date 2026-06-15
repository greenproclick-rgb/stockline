"""
Voice handler for Twilio webhook integration.
"""

import logging
import os
from flask import Flask, request, Response
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from src.ivr.call_manager import CallManager
from src.finnhub.api_client import FinnhubClient
from config.settings import Settings

# Integrated Utilities
from src.ivr.utils import map_t9_to_symbol
from src.api.rss_client import AnalysisClient 

logger = logging.getLogger(__name__)

class VoiceHandler:
    """Handles Twilio webhook callbacks for voice interactions."""
    
    def __init__(self, call_manager: CallManager, settings: Settings):
        """Initialize voice handler."""
        self.call_manager = call_manager
        self.settings = settings
        self.app = Flask(__name__)
        self.setup_routes()
    
    def setup_routes(self):
        """Setup Flask routes for Twilio webhooks."""
        
        @self.app.route('/call/incoming', methods=['POST'])
        def handle_incoming_call():
            try:
                call_sid = request.form.get('CallSid')
                response = VoiceResponse()
                response.say("Welcome to Stockline.")
                
                gather = Gather(num_digits=1, action=f'/call/menu/{call_sid}', method='POST', timeout=10)
                gather.say("Press 1 for a stock quote and analysis. Press 2 to search. Press 0 to hang up.")
                response.append(gather)
                
                return Response(str(response), mimetype='application/xml')
            except Exception as e:
                logger.error(f"Error handling incoming call: {e}")
                return self._error_response()

        @self.app.route('/call/menu/<call_sid>', methods=['POST'])
        def handle_menu_selection(call_sid):
            digit = request.form.get('Digits', '')
            response = VoiceResponse()
            
            if digit == '1':
                response.say("Enter the stock symbol digits then press pound.")
                response.gather(finish_on_key='#', action=f'/call/get-quote/{call_sid}', method='POST', timeout=10)
            elif digit == '2':
                # FIXED: Now handles option 2 specifically
                response.say("Please say the name of the company.")
                response.gather(input='speech', action=f'/call/search-company/{call_sid}', method='POST', timeout=10)
            elif digit == '0':
                response.say("Goodbye!")
                response.hangup()
            else:
                response.say("Returning to main menu.")
                response.redirect('/call/incoming')
                
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/get-quote/<call_sid>', methods=['POST'])
        def get_stock_quote(call_sid):
            try:
                digits = request.form.get('Digits', '')
                # CRITICAL: Ensure map_t9_to_symbol is correctly imported
                symbol = map_t9_to_symbol(digits) 
                
                response = VoiceResponse()
                if not symbol:
                    response.say("I could not translate those digits into a symbol. Please try again.")
                    response.redirect(f'/call/menu/{call_sid}')
                    return Response(str(response), mimetype='application/xml')

                # Get Price
                quote = self.call_manager.finnhub_client.get_quote(symbol)
                if quote and quote.get('current_price'):
                    price = quote.get('current_price', 0)
                    response.say(f"The price for {symbol} is {price:.2f} dollars.")
                    
                    # Try RSS Analysis but wrap in try/except so it doesn't crash the whole call
                    try:
                        rss = AnalysisClient()
                        analysis_text = rss.get_latest_news(symbol)
                        response.say(analysis_text, voice='Polly.Joanna')
                    except Exception as rss_err:
                        logger.error(f"RSS failed: {rss_err}")
                        response.say("Analysis for this stock is currently unavailable.")
                else:
                    response.say(f"Finnhub could not find data for symbol {symbol}.")

                response.say("Press 1 for another quote, or 0 to hang up.")
                response.gather(num_digits=1, action=f'/call/menu/{call_sid}')
                return Response(str(response), mimetype='application/xml')
            except Exception as e:
                logger.error(f"Quote Error: {e}")
                return self._error_response()

        @self.app.route('/call/end', methods=['POST'])
        def end_call():
            return Response("OK", status=200)

    def _error_response(self):
        response = VoiceResponse()
        response.say("A system error occurred. Please try again later.")
        response.hangup()
        return Response(str(response), mimetype='application/xml')
