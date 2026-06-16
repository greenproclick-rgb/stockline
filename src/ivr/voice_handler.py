from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import requests
import logging
from src.api.rss_client import AnalysisClient
from .voice_handler import VoiceHandler # If needed, but usually not inside itself
from src.api.rss_client import AnalysisClient
from src.utils.t9_decoder import map_t9_to_symbol

logger = logging.getLogger(__name__)

class VoiceHandler:
    def __init__(self, call_manager, settings):
        self.call_manager = call_manager
        self.settings = settings
        self.app = Flask(__name__)
        self.fmp_key = settings.fmp_api_key
        self.setup_routes()

    def setup_routes(self):
        # 1. MAIN MENU
        @self.app.route('/call/incoming', methods=['POST'])
        def handle_incoming_call():
            response = VoiceResponse()
            response.say("Welcome to Stockline.")
            gather = Gather(num_digits=1, action='/call/menu', method='POST', timeout=10)
            gather.say("Press 1 for stock quotes. Press 2 for voice search. Press 3 for market movers. Press 4 for market recap. Press star at any time to return here.")
            response.append(gather)
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/menu', methods=['POST'])
        def handle_menu_selection():
            digit = request.form.get('Digits', '')
            response = VoiceResponse()
            
            if digit == '1':
                gather = Gather(num_digits=10, finish_on_key='#', action='/call/get-quote', method='POST', timeout=15)
                gather.say("Enter symbol digits followed by pound. For example, for Apple, press 2 1 2 1 7 1 5 3 pound.")
                response.append(gather)
            elif digit == '3':
                gather = Gather(num_digits=1, action='/call/movers-menu', method='POST', timeout=10)
                gather.say("For top gainers, press 1. For top losers, press 2. For trending and active, press 3.")
                response.append(gather)
            elif digit == '4':
                response.redirect('/call/market-recap')
            elif digit == '*':
                response.redirect('/call/incoming')
            else:
                response.say("Invalid selection.")
                response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 2. STICKY QUOTE LOGIC
        @self.app.route('/call/get-quote', methods=['POST'])
        def get_stock_quote():
            digits = request.form.get('Digits', '')
            symbol = request.args.get('symbol') or map_t9_to_symbol(digits)
            call_sid = request.form.get('CallSid')
            response = VoiceResponse()
            
            try:
                quote = self.call_manager.finnhub_client.get_quote(symbol)
                price = quote.get('c', 0)
                change = quote.get('dp', 0)
                
                if price == 0:
                    response.say(f"I'm sorry, I couldn't find a quote for {symbol}.")
                    response.redirect('/call/incoming')
                else:
                    response.say(f"{symbol} is trading at {price} dollars, {'up' if change >= 0 else 'down'} {abs(change):.2f} percent.")
                    
                    # STICKY MENU
                    gather = Gather(num_digits=1, action=f'/call/quote-options?symbol={symbol}', method='POST', timeout=15)
                    gather.say("Press 1 for latest analysis. Press 2 for key financials and target price. Press star to go back.")
                    response.append(gather)
            except Exception as e:
                logger.error(f"Quote error: {e}")
                response.say("Error retrieving quote data.")
                response.redirect('/call/incoming')
                
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/quote-options', methods=['POST'])
        def quote_options():
            symbol = request.args.get('symbol')
            digit = request.form.get('Digits', '')
            response = VoiceResponse()
            
            if digit == '1': # ANALYSIS
                rss = AnalysisClient()
                news = rss.get_latest_news(symbol)
                response.say(news)
                response.redirect(f'/call/get-quote?symbol={symbol}') # Loop back
            elif digit == '2': # FINANCIALS
                try:
                    url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={self.fmp_key}"
                    data = requests.get(url, timeout=5).json()
                    if data:
                        s = data[0]
                        response.say(f"{symbol} fifty two week range is {s['yearLow']} to {s['yearHigh']}. "
                                     f"Average volume is {s['avgVolume']}. Market cap is {s['marketCap']}. "
                                     f"The day high is {s['dayHigh']} and the day low is {s['dayLow']}.")
                    else:
                        response.say("Financial details not found.")
                except:
                    response.say("Unable to reach financials server.")
                response.redirect(f'/call/get-quote?symbol={symbol}') # Loop back
            elif digit == '*':
                response.redirect('/call/incoming')
            else:
                response.redirect(f'/call/get-quote?symbol={symbol}')
                
            return Response(str(response), mimetype='application/xml')

        # 3. MARKET MOVERS
        @self.app.route('/call/movers-menu', methods=['POST'])
        def movers_menu():
            digit = request.form.get('Digits', '')
            response = VoiceResponse()
            
            endpoint = "gainers" if digit == '1' else "losers" if digit == '2' else "actives"
            try:
                url = f"https://financialmodelingprep.com/api/v3/{endpoint}?apikey={self.fmp_key}"
                data = requests.get(url, timeout=5).json()
                response.say(f"Here are the top three {endpoint} items.")
                for stock in data[:3]:
                    response.say(f"{stock['symbol']}, {stock['changesPercentage']} percent.")
            except:
                response.say("Movers data is currently unavailable.")
            
            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 4. MARKET RECAP
        @self.app.route('/call/market-recap', methods=['POST'])
        def market_recap():
            response = VoiceResponse()
            try:
                rss = AnalysisClient()
                recap = rss.get_top_gainers() # MarketWatch or Investing.com RSS
                response.say(recap)
            except:
                response.say("Market recap is currently unavailable.")
            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

    def _error_response(self):
        response = VoiceResponse()
        response.say("An unexpected error occurred. Returning to the main menu.")
        response.redirect('/call/incoming')
        return Response(str(response), mimetype='application/xml')
