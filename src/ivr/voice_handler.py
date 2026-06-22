from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import requests
import logging
from src.api.rss_client import AnalysisClient
from src.ivr.utils import map_t9_to_symbol 

logger = logging.getLogger(__name__)

class VoiceHandler:
    def __init__(self, call_manager, settings):
        self.call_manager = call_manager
        self.settings = settings
        self.app = Flask(__name__)
        # FORCE RE-READ FROM OS TO BE SAFE
        import os
        self.fmp_key = os.getenv('FMP_API_KEY')
        self.setup_routes()

    def setup_routes(self):
        @self.app.route('/call/incoming', methods=['POST'])
        def handle_incoming_call():
            response = VoiceResponse()
            response.say("Welcome to Stockline.")
            gather = Gather(num_digits=1, action='/call/menu', method='POST', timeout=10)
            gather.say("Press 1 for stock quotes. Press 3 for market movers. Press 4 for market recap.")
            response.append(gather)
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/menu', methods=['POST'])
        def handle_menu_selection():
            digit = request.form.get('Digits', '')
            response = VoiceResponse()
            if digit == '1':
                gather = Gather(num_digits=10, finish_on_key='#', action='/call/get-quote', method='POST', timeout=15)
                gather.say("Enter symbol digits followed by pound.")
                response.append(gather)
            elif digit == '3':
                gather = Gather(num_digits=1, action='/call/movers-menu', method='POST', timeout=10)
                gather.say("For top gainers, press 1. For top losers, press 2. For actives, press 3.")
                response.append(gather)
            else:
                response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/get-quote', methods=['POST'])
        def get_stock_quote():
            digits = request.form.get('Digits', '').replace('#', '') # Clean digits
            # LOGGING THE DIGITS TO RAILWAY
            logger.info(f"Received digits: {digits}")
            
            symbol = map_t9_to_symbol(digits)
            response = VoiceResponse()
            
            if not symbol:
                logger.error(f"T9 mapping failed for digits: {digits}")
                response.say("I could not identify that stock symbol.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            symbol = symbol.upper()
            try:
                quote = self.call_manager.finnhub_client.get_quote(symbol)
                price = quote.get('c', 0)
                if price == 0:
                    response.say(f"No price found for {symbol}.")
                else:
                    response.say(f"{symbol} is at {price} dollars.")
                    gather = Gather(num_digits=1, action=f'/call/quote-options?symbol={symbol}', method='POST')
                    gather.say("Press 1 for analysis. Press 2 for financials.")
                    response.append(gather)
            except:
                response.say("Finance service busy.")
            
            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/movers-menu', methods=['POST'])
        def movers_menu():
            digit = request.form.get('Digits', '')
            response = VoiceResponse()
            
            # FMP Key Check
            if not self.fmp_key:
                response.say("Movers key is missing in system variables.")
                return Response(str(response), mimetype='application/xml')

            endpoint = "gainers" if digit == '1' else "losers" if digit == '2' else "actives"
            try:
                # API Key is passed as 'apikey' (all lowercase, no dash)
                url = f"https://financialmodelingprep.com/api/v3/stock_market/{endpoint}?apikey={self.fmp_key}"
                r = requests.get(url, timeout=5)
                data = r.json()
                
                if isinstance(data, dict) and ("Error" in str(data)):
                    response.say("The data provider declined the access key.")
                else:
                    response.say(f"Here are the top three {endpoint}.")
                    for stock in data[:3]:
                        response.say(f"{stock['symbol']}, {stock['changesPercentage']} percent.")
            except:
                response.say("Could not connect to movers service.")
            
            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')
