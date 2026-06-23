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
        # ENSURE THIS MATCHES YOUR settings.py VARIABLE NAME
        self.fmp_key = getattr(settings, 'fmp_api_key', None) 
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
                gather.say("Enter symbol digits followed by pound.")
                response.append(gather)
            elif digit == '3':
                gather = Gather(num_digits=1, action='/call/movers-menu', method='POST', timeout=10)
                gather.say("For top gainers, press 1. For top losers, press 2. For actives, press 3.")
                response.append(gather)
            elif digit == '4':
                response.redirect('/call/market-recap')
            else:
                response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 2. QUOTE LOGIC (Uses FinancialModelingPrep API with fallback)
        @self.app.route('/call/get-quote', methods=['POST'])
        def get_stock_quote():
            digits = request.form.get('Digits', '')
            raw_symbol = request.args.get('symbol') or map_t9_to_symbol(digits)
            
            if not raw_symbol:
                response = VoiceResponse()
                response.say("I could not understand that symbol.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            symbol = raw_symbol.upper()  # FMP expects uppercase symbols
            response = VoiceResponse()

            if not self.fmp_key:
                logger.error("FMP_API_KEY is missing in VoiceHandler for get-quote!")
                response.say("Internal configuration error. API key not found.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            try:
                url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={self.fmp_key}"
                r = requests.get(url, timeout=5)

                # If non-200, inspect and try fallback
                if r.status_code != 200:
                    logger.error(f"FMP HTTP {r.status_code} for quote {symbol}: {r.text}")
                    # Detect legacy-endpoint error message in body
                    try:
                        body = r.json()
                    except Exception:
                        body = None

                    legacy_msg = None
                    if isinstance(body, dict):
                        # common shapes
                        legacy_msg = body.get('Error Message') or body.get('error') or body.get('message')

                    if legacy_msg and 'Legacy Endpoint' in legacy_msg:
                        logger.info("FMP legacy endpoint detected, attempting Finnhub fallback if configured")
                        # Attempt Finnhub fallback if available
                        try:
                            fh_client = getattr(self.call_manager, 'finnhub_client', None)
                            if fh_client:
                                fh_quote = fh_client.get_quote(symbol)
                                if fh_quote and fh_quote.get('current_price'):
                                    price = fh_quote.get('current_price')
                                    response.say(f"{symbol} is trading at {price:.2f} dollars.")
                                    gather = Gather(num_digits=1, action=f'/call/quote-options?symbol={symbol}', method='POST', timeout=15)
                                    gather.say("Press 1 for analysis. Press 2 for financials. Press star to go back.")
                                    response.append(gather)
                                    return Response(str(response), mimetype='application/xml')
                        except Exception as e:
                            logger.error(f"Finnhub fallback error: {e}")

                        response.say("The financial data provider rejected the request. Please update the configured API or try again later.")
                        response.redirect('/call/incoming')
                        return Response(str(response), mimetype='application/xml')

                    # Other non-200 errors
                    response.say("The financial data provider rejected the request.")
                    response.redirect('/call/incoming')
                    return Response(str(response), mimetype='application/xml')

                data = r.json()
                logger.debug(f"FMP quote response for {symbol}: {data}")

                # FMP returns a list for the quote endpoint: [] or [{...}]
                if isinstance(data, dict):
                    # handle error shapes like {"Error Message": "..."} or {"error":"..."}
                    if data.get("Error Message") or data.get('error') or data.get('message'):
                        logger.error(f"FMP API Error for {symbol}: {data}")
                        response.say("The financial data provider rejected the request.")
                        response.redirect('/call/incoming')
                        return Response(str(response), mimetype='application/xml')

                if not data or (isinstance(data, list) and len(data) == 0):
                    response.say(f"I'm sorry, I couldn't find a quote for {symbol}.")
                    response.redirect('/call/incoming')
                    return Response(str(response), mimetype='application/xml')

                quote = data[0] if isinstance(data, list) else data
                raw_price = quote.get('price')
                try:
                    price = float(raw_price) if raw_price is not None else 0
                except (TypeError, ValueError):
                    price = 0

                if price == 0:
                    response.say(f"I'm sorry, I couldn't find a quote for {symbol}.")
                    response.redirect('/call/incoming')
                else:
                    response.say(f"{symbol} is trading at {price:.2f} dollars.")
                    gather = Gather(num_digits=1, action=f'/call/quote-options?symbol={symbol}', method='POST', timeout=15)
                    gather.say("Press 1 for analysis. Press 2 for financials. Press star to go back.")
                    response.append(gather)
            except Exception as e:
                logger.error(f"FMP Error: {e}")
                response.say("Error reaching the quote service.")
                response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 3. FIXED MOVERS (Adds API Key Check and error handling)
        @self.app.route('/call/movers-menu', methods=['POST'])
        def movers_menu():
            digit = request.form.get('Digits', '')
            response = VoiceResponse()
            
            if not self.fmp_key:
                logger.error("FMP_API_KEY is missing in VoiceHandler!")
                response.say("Internal configuration error. API key not found.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            endpoint = "gainers" if digit == '1' else "losers" if digit == '2' else "actives"
            try:
                url = f"https://financialmodelingprep.com/api/v3/{endpoint}?apikey={self.fmp_key}"
                r = requests.get(url, timeout=5)

                if r.status_code != 200:
                    logger.error(f"FMP HTTP {r.status_code} for {endpoint}: {r.text}")
                    try:
                        body = r.json()
                    except Exception:
                        body = None

                    legacy_msg = None
                    if isinstance(body, dict):
                        legacy_msg = body.get('Error Message') or body.get('error') or body.get('message')

                    if legacy_msg and 'Legacy Endpoint' in legacy_msg:
                        logger.info("FMP legacy endpoint detected for movers; no fallback available")
                        response.say("Market movers are not available from the configured provider. Please update your API subscription or try again later.")
                        response.redirect('/call/incoming')
                        return Response(str(response), mimetype='application/xml')

                    response.say("The financial data provider rejected the request.")
                    response.redirect('/call/incoming')
                    return Response(str(response), mimetype='application/xml')

                data = r.json()
                
                if isinstance(data, dict) and (data.get('Error Message') or data.get('error') or data.get('message')):
                    logger.error(f"FMP API Error: {data}")
                    response.say("The financial data provider rejected the request.")
                else:
                    response.say(f"Here are the top three {endpoint}.")
                    for stock in data[:3]:
                        response.say(f"{stock.get('symbol')}, {stock.get('changesPercentage')} percent.")
            except Exception as e:
                logger.error(f"FMP Connection Error: {e}")
                response.say("Movers data is currently unavailable.")
            
            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 4. MARKET RECAP
        @self.app.route('/call/market-recap', methods=['POST'])
        def market_recap():
            response = VoiceResponse()
            try:
                rss = AnalysisClient()
                recap = rss.get_top_gainers()
                response.say(recap)
            except:
                response.say("Market recap is currently unavailable.")
            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')
