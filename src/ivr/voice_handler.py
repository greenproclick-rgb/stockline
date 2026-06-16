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

# Utilities and RSS
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
                
                # Menu Gather
                gather = Gather(num_digits=1, action=f'/call/menu/{call_sid}', method='POST', timeout=10)
                gather.say("Press 1 for quote and analysis. Press 2 to search. Press 3 for market gainers. Press 0 to hang up.")
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
                # Stock Quote logic using T9 pairs (A=21, I=43)
                gather = Gather(num_digits=10, finish_on_key='#', action=f'/call/get-quote/{call_sid}', method='POST', timeout=15)
                gather.say("Enter symbol digits followed by pound. For A press 2 1. For I press 4 3.")
                response.append(gather)
            
            elif digit == '2':
                # Speech search logic
                gather = Gather(input='speech', action=f'/call/search-company/{call_sid}', method='POST', timeout=5)
                gather.say("Please say the company name clearly.")
                response.append(gather)

            elif digit == '3':
                # Market Gainers Logic
                response.say("Fetching market movers.")
                try:
                    rss = AnalysisClient()
                    summary = rss.get_top_gainers()
                    response.say(summary, voice='Polly.Joanna')
                except:
                    response.say("Market info is temporarily unavailable.")
                response.redirect('/call/incoming')

            elif digit == '0':
                response.say("Goodbye!")
                response.hangup()
            
            else:
                response.say("Invalid selection.")
                response.redirect('/call/incoming')

            # Ensure this return is aligned at the function level
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/get-quote/<call_sid>', methods=['POST'])
        def get_stock_quote(call_sid):
            try:
                digits = request.form.get('Digits', '')
                symbol = map_t9_to_symbol(digits) 
                
                response = VoiceResponse()
                
                if not symbol:
                    response.say("I could not decode those digits. Returning to menu.")
                    response.redirect(f'/call/menu/{call_sid}')
                    return Response(str(response), mimetype='application/xml')

                # Get Price from Finnhub
                quote = self.call_manager.finnhub_client.get_quote(symbol)
                if quote and quote.get('current_price'):
                    price = quote.get('current_price', 0)
                    response.say(f"The price for {symbol} is {price:.2f} dollars.")
                    
                    # Try Seeking Alpha Analysis
                    try:
                        rss = AnalysisClient()
                        analysis_text = rss.get_latest_news(symbol)
                        response.say(analysis_text, voice='Polly.Joanna')
                    except Exception as rss_err:
                        logger.error(f"RSS failed: {rss_err}")
                        response.say("Analysis for this stock is currently unavailable.")
                else:
                    response.say(f"I found the symbol {symbol}, but no price data is available.")

                response.say("Press 1 for another quote, or 0 to return to menu.")
                gather = Gather(num_digits=1, action=f'/call/menu/{call_sid}')
                response.append(gather)
                
                return Response(str(response), mimetype='application/xml')
            except Exception as e:
                logger.error(f"Quote Error: {e}")
                return self._error_response()

        @self.app.route('/call/search-company/<call_sid>', methods=['POST'])
        def search_company(call_sid):
            try:
                company_name = request.form.get('SpeechResult', '')
                response = VoiceResponse()
                
                if company_name:
                    results = self.call_manager.finnhub_client.search_symbol(company_name)
                    if results:
                        symbol = results[0].get('symbol', '')
                        desc = results[0].get('description', '')
                        response.say(f"I found {desc}. The symbol is {symbol}.")
                        response.say("Press 1 to get the price, or 0 to return.")
                        gather = Gather(num_digits=1, action=f'/call/search-result/{call_sid}/{symbol}')
                        response.append(gather)
                    else:
                        response.say(f"No results for {company_name}.")
                        response.redirect('/call/incoming')
                else:
                    response.redirect('/call/incoming')
                
                return Response(str(response), mimetype='application/xml')
            except Exception as e:
                logger.error(f"Search error: {e}")
                return self._error_response()

        @self.app.route('/call/search-result/<call_sid>/<symbol>', methods=['POST'])
        def handle_search_result(call_sid, symbol):
            digit = request.form.get('Digits', '')
            response = VoiceResponse()
            if digit == '1':
                # Fetch price for the searched symbol
                quote = self.call_manager.finnhub_client.get_quote(symbol)
                if quote:
                    price = quote.get('current_price', 0)
                    response.say(f"{symbol} is trading at {price:.2f} dollars.")
            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/end', methods=['POST'])
        def end_call():
            return Response("OK", status=200)

    def _error_response(self):
        """Standard error handler."""
        response = VoiceResponse()
        response.say("I'm sorry, a system error occurred. Please try again later.")
        response.hangup()
        return Response(str(response), mimetype='application/xml')

    def run(self, host='0.0.0.0', port=5000, debug=False):
        self.app.run(host=host, port=port, debug=debug)
