"""
Voice handler for Twilio webhook integration.
"""

import logging
from flask import Flask, request, Response
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from src.ivr.call_manager import CallManager
from src.finnhub.api_client import FinnhubClient
from config.settings import Settings
import os

logger = logging.getLogger(__name__)

class VoiceHandler:
    """Handles Twilio webhook callbacks for voice interactions."""
    
    def __init__(self, call_manager: CallManager, settings: Settings):
        """Initialize voice handler.
        
        Args:
            call_manager: CallManager instance
            settings: Application settings
        """
        self.call_manager = call_manager
        self.settings = settings
        self.app = Flask(__name__)
        self.setup_routes()
    
    def setup_routes(self):
        """Setup Flask routes for Twilio webhooks."""
        
        @self.app.route('/call/incoming', methods=['POST'])
        def handle_incoming_call():
            """Handle incoming call webhook."""
            try:
                call_sid = request.form.get('CallSid')
                from_number = request.form.get('From')
                to_number = request.form.get('To')
                
                logger.info(f"Incoming call from {from_number} to {to_number}")
                
                # Handle the call
                self.call_manager.handle_incoming_call(call_sid, from_number, to_number)
                
                # Generate TwiML response
                response = VoiceResponse()
                response.say("Welcome to Stockline. Press 1 for a stock quote, 2 to search for a company, "
                           "3 for market summary, or 0 to hang up.")
                response.gather(
                    num_digits=1,
                    action=f'/call/menu/{call_sid}',
                    method='POST',
                    timeout=10
                )
                
                return Response(str(response), mimetype='application/xml')
            
            except Exception as e:
                logger.error(f"Error handling incoming call: {e}")
                response = VoiceResponse()
                response.say("Sorry, there was an error. Please try again later.")
                response.hangup()
                return Response(str(response), mimetype='application/xml')
        
        @self.app.route('/call/menu/<call_sid>', methods=['POST'])
        def handle_menu_selection(call_sid):
            """Handle menu selection from caller."""
            try:
                digit = request.form.get('Digits', '')
                logger.info(f"Menu selection {digit} for call {call_sid}")
                
                response = VoiceResponse()
                
                if digit == '1':
                    # Stock quote - prompt for symbol
                    response.say("Please enter the stock symbol you want to check. Press star when done.")
                    response.gather(
                        num_digits=5,
                        action=f'/call/get-quote/{call_sid}',
                        method='POST',
                        timeout=10
                    )
                
                elif digit == '2':
                    # Company search
                    response.say("Please enter the company name. Press star when done.")
                    response.gather(
                        num_digits=5,
                        action=f'/call/search-company/{call_sid}',
                        method='POST',
                        timeout=10
                    )
                
                elif digit == '3':
                    # Market summary
                    response.say("Market overview: The S&P 500 is up 0.5 percent today.")
                    response.say("Press 1 for another quote, or 0 to hang up.")
                    response.gather(
                        num_digits=1,
                        action=f'/call/menu/{call_sid}',
                        method='POST',
                        timeout=10
                    )
                
                elif digit == '0':
                    # Hangup
                    response.say("Thank you for using Stockline. Goodbye!")
                    response.hangup()
                
                else:
                    # Invalid selection
                    response.say("Invalid selection. Please try again.")
                    response.say("Press 1 for a stock quote, 2 to search, 3 for market summary, or 0 to hang up.")
                    response.gather(
                        num_digits=1,
                        action=f'/call/menu/{call_sid}',
                        method='POST',
                        timeout=10
                    )
                
                return Response(str(response), mimetype='application/xml')
            
            except Exception as e:
                logger.error(f"Error handling menu selection: {e}")
                response = VoiceResponse()
                response.say("Sorry, there was an error. Please try again.")
                response.hangup()
                return Response(str(response), mimetype='application/xml')
        
        @self.app.route('/call/get-quote/<call_sid>', methods=['POST'])
        def get_stock_quote(call_sid):
            """Get stock quote for caller."""
            try:
                symbol = request.form.get('SpeechResult', request.form.get('Digits', '')).upper()
                logger.info(f"Getting quote for {symbol} (call {call_sid})")
                
                response = VoiceResponse()
                
                if symbol:
                    # Fetch quote from Finnhub
                    quote = self.call_manager.finnhub_client.get_quote(symbol)
                    
                    if quote:
                        price = quote.get('current_price', 0)
                        change = price - quote.get('previous_close', price)
                        change_percent = (change / quote.get('previous_close', 1)) * 100 if quote.get('previous_close') else 0
                        
                        direction = "up" if change >= 0 else "down"
                        abs_change = abs(change)
                        
                        message = (f"{symbol} is trading at ${price:.2f}, {direction} "
                                 f"${abs_change:.2f} or {change_percent:.2f} percent.")
                        response.say(message)
                    else:
                        response.say(f"Sorry, I could not find data for {symbol}. Please try again.")
                else:
                    response.say("No symbol was entered. Please try again.")
                
                # Return to menu
                response.say("Press 1 for another quote, or 0 to hang up.")
                response.gather(
                    num_digits=1,
                    action=f'/call/menu/{call_sid}',
                    method='POST',
                    timeout=10
                )
                
                return Response(str(response), mimetype='application/xml')
            
            except Exception as e:
                logger.error(f"Error getting stock quote: {e}")
                response = VoiceResponse()
                response.say("Sorry, there was an error retrieving the quote. Please try again.")
                response.hangup()
                return Response(str(response), mimetype='application/xml')
        
        @self.app.route('/call/search-company/<call_sid>', methods=['POST'])
        def search_company(call_sid):
            """Search for company by name."""
            try:
                company_name = request.form.get('SpeechResult', request.form.get('Digits', '')).strip()
                logger.info(f"Searching for company '{company_name}' (call {call_sid})")
                
                response = VoiceResponse()
                
                if company_name:
                    results = self.call_manager.finnhub_client.search_symbol(company_name)
                    
                    if results:
                        first_result = results[0]
                        symbol = first_result.get('symbol', '')
                        description = first_result.get('description', '')
                        
                        response.say(f"Found {description}. The stock symbol is {symbol}.")
                        response.say("Press 1 to get a quote for this stock, or 0 to return to menu.")
                        response.gather(
                            num_digits=1,
                            action=f'/call/search-result/{call_sid}/{symbol}',
                            method='POST',
                            timeout=10
                        )
                    else:
                        response.say(f"No companies found matching {company_name}. Please try again.")
                        response.say("Press 2 to search again, or 0 to return to menu.")
                        response.gather(
                            num_digits=1,
                            action=f'/call/menu/{call_sid}',
                            method='POST',
                            timeout=10
                        )
                else:
                    response.say("No company name was entered. Please try again.")
                
                return Response(str(response), mimetype='application/xml')
            
            except Exception as e:
                logger.error(f"Error searching company: {e}")
                response = VoiceResponse()
                response.say("Sorry, there was an error during the search. Please try again.")
                response.hangup()
                return Response(str(response), mimetype='application/xml')
        
        @self.app.route('/call/search-result/<call_sid>/<symbol>', methods=['POST'])
        def handle_search_result(call_sid, symbol):
            """Handle search result selection."""
            try:
                digit = request.form.get('Digits', '')
                response = VoiceResponse()
                
                if digit == '1':
                    # Get quote for selected stock
                    quote = self.call_manager.finnhub_client.get_quote(symbol)
                    
                    if quote:
                        price = quote.get('current_price', 0)
                        change = price - quote.get('previous_close', price)
                        change_percent = (change / quote.get('previous_close', 1)) * 100 if quote.get('previous_close') else 0
                        
                        direction = "up" if change >= 0 else "down"
                        abs_change = abs(change)
                        
                        message = (f"{symbol} is trading at ${price:.2f}, {direction} "
                                 f"${abs_change:.2f} or {change_percent:.2f} percent.")
                        response.say(message)
                    else:
                        response.say(f"Could not retrieve quote for {symbol}.")
                
                # Return to menu
                response.say("Press 1 for another quote, or 0 to hang up.")
                response.gather(
                    num_digits=1,
                    action=f'/call/menu/{call_sid}',
                    method='POST',
                    timeout=10
                )
                
                return Response(str(response), mimetype='application/xml')
            
            except Exception as e:
                logger.error(f"Error handling search result: {e}")
                response = VoiceResponse()
                response.say("Sorry, there was an error. Please try again.")
                response.hangup()
                return Response(str(response), mimetype='application/xml')
        
        @self.app.route('/call/end', methods=['POST'])
        def end_call():
            """Handle call end webhook."""
            try:
                call_sid = request.form.get('CallSid')
                logger.info(f"Call ended: {call_sid}")
                self.call_manager._end_call(call_sid)
                return Response("OK", status=200)
            except Exception as e:
                logger.error(f"Error ending call: {e}")
                return Response("ERROR", status=500)
    
    def run(self, host='0.0.0.0', port=5000, debug=False):
        """Run the Flask application.
        
        Args:
            host: Host to bind to
            port: Port to listen on
            debug: Enable debug mode
        """
        logger.info(f"Starting voice handler on {host}:{port}")
        self.app.run(host=host, port=port, debug=debug)
