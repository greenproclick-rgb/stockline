from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import requests
import logging

logger = logging.getLogger(__name__)

class VoiceHandler:
    def __init__(self, call_manager, settings):
        self.call_manager = call_manager
        self.settings = settings
        self.app = Flask(__name__)
        self.fmp_key = settings.fmp_api_key # Your FMP Key
        self.setup_routes()

    def setup_routes(self):
        # 1. MAIN MENU
        @self.app.route('/call/incoming', methods=['POST'])
        def handle_incoming_call():
            response = VoiceResponse()
            response.say("Welcome to Stockline.")
            gather = Gather(num_digits=1, action='/call/menu')
            gather.say("Press 1 for stock quotes. Press 2 for voice search. Press 3 for market movers. Press 4 for market recap.")
            response.append(gather)
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/menu', methods=['POST'])
        def handle_menu_selection():
            digit = request.form.get('Digits', '')
            response = VoiceResponse()
            
            if digit == '1':
                gather = Gather(num_digits=10, finish_on_key='#', action='/call/get-quote')
                gather.say("Enter symbol digits followed by pound.")
                response.append(gather)
            elif digit == '3':
                gather = Gather(num_digits=1, action='/call/movers-menu')
                gather.say("For top gainers, press 1. For losers, press 2. For trending, press 3.")
                response.append(gather)
            elif digit == '4':
                response.redirect('/call/market-recap')
            elif digit == '*':
                response.redirect('/call/incoming')
            else:
                response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 2. THE STICKY QUOTE MENU (HANDLES 1 AND 2)
        @self.app.route('/call/get-quote', methods=['POST'])
        def get_stock_quote():
            digits = request.form.get('Digits', '')
            # If we are coming back from a sub-menu, we might pass symbol in URL
            symbol = request.args.get('symbol') or map_t9_to_symbol(digits)
            
            response = VoiceResponse()
            # Fetch price and change %
            quote = self.call_manager.finnhub_client.get_quote(symbol)
            price = quote.get('c', 0)
            change = quote.get('dp', 0)
            
            response.say(f"{symbol} is at {price} dollars, {'up' if change >=0 else 'down'} {abs(change):.2f} percent.")
            
            # THE STICKY OPTIONS
            gather = Gather(num_digits=1, action=f'/call/quote-options?symbol={symbol}')
            gather.say("Press 1 for analysis. Press 2 for financials. Press star to go back.")
            response.append(gather)
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
                # Redirect back to the SAME sticky menu
                response.redirect(f'/call/get-quote?symbol={symbol}')
            elif digit == '2': # FINANCIALS (FMP API)
                data = requests.get(f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={self.fmp_key}").json()
                if data:
                    s = data[0]
                    response.say(f"Fifty two week range is {s['yearLow']} to {s['yearHigh']}. "
                                 f"Average volume is {s['avgVolume']}. Market cap is {s['marketCap']}.")
                response.redirect(f'/call/get-quote?symbol={symbol}')
            else:
                response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 3. MARKET MOVERS (FMP API)
        @self.app.route('/call/movers-menu', methods=['POST'])
        def movers_menu():
            digit = request.form.get('Digits', '')
            response = VoiceResponse()
            
            endpoint = "gainers" if digit == '1' else "losers" if digit == '2' else "actives"
            data = requests.get(f"https://financialmodelingprep.com/api/v3/{endpoint}?apikey={self.fmp_key}").json()
            
            response.say(f"Here are the top {endpoint}:")
            for stock in data[:3]:
                response.say(f"{stock['symbol']}, {stock['changesPercentage']}%")
            
            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 4. MARKET RECAP
        @self.app.route('/call/market-recap', methods=['POST'])
        def market_recap():
            response = VoiceResponse()
            rss = AnalysisClient()
            recap = rss.get_top_gainers() # MarketWatch RSS
            response.say(recap)
            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

    def _error_response(self):
        response = VoiceResponse()
        response.say("A connection error occurred. Returning to main menu.")
        response.redirect('/call/incoming')
        return Response(str(response), mimetype='application/xml')
