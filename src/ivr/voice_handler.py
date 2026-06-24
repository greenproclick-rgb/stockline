from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import logging
from src.api.rss_client import AnalysisClient
from src.ivr.utils import map_t9_to_symbol

logger = logging.getLogger(__name__)

class VoiceHandler:
    def __init__(self, call_manager, settings):
        self.call_manager = call_manager
        self.settings = settings
        self.app = Flask(__name__)
        self.finnhub_client = getattr(call_manager, 'finnhub_client', None)
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

        # 2. QUOTE FLOW — uses Finnhub
        @self.app.route('/call/get-quote', methods=['POST'])
        def get_stock_quote():
            digits = request.form.get('Digits', '')
            raw_symbol = request.args.get('symbol') or map_t9_to_symbol(digits)

            response = VoiceResponse()

            if not raw_symbol:
                response.say("I could not understand that symbol.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            symbol = raw_symbol.upper()

            if not self.finnhub_client:
                logger.error("Finnhub client not available in VoiceHandler.")
                response.say("Internal configuration error. Please try again later.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            try:
                quote = self.finnhub_client.get_quote(symbol)
                logger.debug(f"Finnhub quote for {symbol}: {quote}")

                if not quote:
                    response.say(f"I'm sorry, I couldn't find a quote for {symbol}.")
                    response.redirect('/call/incoming')
                    return Response(str(response), mimetype='application/xml')

                price = quote.get('current_price') or 0
                try:
                    price = float(price)
                except (TypeError, ValueError):
                    price = 0

                if price == 0:
                    response.say(f"I'm sorry, I couldn't find a quote for {symbol}.")
                    response.redirect('/call/incoming')
                else:
                    response.say(f"{symbol} is trading at {price:.2f} dollars.")
                    gather = Gather(num_digits=1, action=f'/call/quote-options?symbol={symbol}', method='POST', timeout=15)
                    gather.say("Press 1 for full details. Press 2 for analysis and news. Press star for the main menu.")
                    response.append(gather)
            except Exception as e:
                logger.error(f"Error fetching quote for {symbol}: {e}")
                response.say("Error reaching the quote service. Please try again.")
                response.redirect('/call/incoming')

            return Response(str(response), mimetype='application/xml')

        # 2a. QUOTE FOLLOW-UP OPTIONS
        @self.app.route('/call/quote-options', methods=['POST'])
        def quote_options():
            digit = request.form.get('Digits', '')
            symbol = request.args.get('symbol', '')
            response = VoiceResponse()

            if digit == '1':
                response.redirect(f'/call/quote-info?symbol={symbol}')
            elif digit == '2':
                response.redirect(f'/call/quote-analysis?symbol={symbol}')
            else:
                response.redirect('/call/incoming')

            return Response(str(response), mimetype='application/xml')

        # 2b. ALL AVAILABLE INFO for a symbol
        @self.app.route('/call/quote-info', methods=['POST', 'GET'])
        def quote_info():
            symbol = request.args.get('symbol', '').upper()
            response = VoiceResponse()

            if not symbol:
                response.say("No symbol provided.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            if not self.finnhub_client:
                response.say("Internal configuration error. Please try again later.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            parts = []

            try:
                financials = self.finnhub_client.get_basic_financials(symbol)
                if financials:
                    w52h = financials.get('week_52_high')
                    w52l = financials.get('week_52_low')
                    pe = financials.get('pe_ratio')
                    if w52h is not None and w52l is not None:
                        parts.append(f"52-week range: {float(w52l):.2f} to {float(w52h):.2f} dollars.")
                    if pe is not None:
                        parts.append(f"Price to earnings ratio: {float(pe):.2f}.")
            except Exception as e:
                logger.error(f"Error fetching basic financials for {symbol}: {e}")

            try:
                price_target = self.finnhub_client.get_price_target(symbol)
                if price_target and price_target.get('target_price') is not None:
                    parts.append(f"Analyst price target: {float(price_target['target_price']):.2f} dollars.")
            except Exception as e:
                logger.error(f"Error fetching price target for {symbol}: {e}")

            try:
                recs = self.finnhub_client.get_recommendation_trends(symbol)
                if recs:
                    buy_total = (recs.get('buy') or 0) + (recs.get('strong_buy') or 0)
                    hold_total = recs.get('hold') or 0
                    sell_total = (recs.get('sell') or 0) + (recs.get('strong_sell') or 0)
                    parts.append(f"Analyst ratings: {buy_total} buy, {hold_total} hold, {sell_total} sell.")
            except Exception as e:
                logger.error(f"Error fetching recommendations for {symbol}: {e}")

            if parts:
                response.say(f"Here is the available information for {symbol}. " + " ".join(parts))
            else:
                response.say(f"Detailed information for {symbol} is not available at this time.")

            gather = Gather(num_digits=1, action=f'/call/quote-options?symbol={symbol}', method='POST', timeout=10)
            gather.say("Press 1 to hear this info again. Press 2 for analysis. Press star to return to the main menu.")
            response.append(gather)

            return Response(str(response), mimetype='application/xml')

        # 2c. ANALYSIS / NEWS for a symbol
        @self.app.route('/call/quote-analysis', methods=['POST', 'GET'])
        def quote_analysis():
            symbol = request.args.get('symbol', '').upper()
            response = VoiceResponse()

            if not symbol:
                response.say("No symbol provided.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            try:
                analysis_client = AnalysisClient()
                analysis_text = analysis_client.get_latest_news(symbol)
                response.say(f"Here is the latest analysis for {symbol}. {analysis_text}")
            except Exception as e:
                logger.error(f"Error fetching analysis for {symbol}: {e}")
                response.say(f"Analysis for {symbol} is not available at this time.")

            gather = Gather(num_digits=1, action=f'/call/quote-options?symbol={symbol}', method='POST', timeout=10)
            gather.say("Press 1 for all available info. Press 2 to hear analysis again. Press star to return to the main menu.")
            response.append(gather)

            return Response(str(response), mimetype='application/xml')

        # 3. MARKET MOVERS — uses Finnhub
        @self.app.route('/call/movers-menu', methods=['POST'])
        def movers_menu():
            digit = request.form.get('Digits', '')
            response = VoiceResponse()

            if not self.finnhub_client:
                logger.error("Finnhub client not available in VoiceHandler for movers.")
                response.say("Internal configuration error. Please try again later.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            category_map = {'1': 'gainers', '2': 'losers', '3': 'actives'}
            category = category_map.get(digit, 'actives')
            label = category

            try:
                movers = self.finnhub_client.get_market_movers(category)
                if not movers:
                    response.say(f"Market {label} data is not available at this time.")
                else:
                    response.say(f"Here are the top {label} right now.")
                    for stock in movers:
                        direction = "up" if stock['change_pct'] >= 0 else "down"
                        response.say(
                            f"{stock['symbol']}, {direction} {abs(stock['change_pct']):.2f} percent, "
                            f"trading at {stock['price']:.2f} dollars."
                        )
            except Exception as e:
                logger.error(f"Error fetching market movers ({category}): {e}")
                response.say("Movers data is currently unavailable. Please try again later.")

            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 4. MARKET RECAP — Finnhub news with RSS fallback
        @self.app.route('/call/market-recap', methods=['POST'])
        def market_recap():
            response = VoiceResponse()

            # Try Finnhub general market news first
            if self.finnhub_client:
                try:
                    news_items = self.finnhub_client.get_market_news()
                    if news_items:
                        headlines = [item['headline'] for item in news_items if item.get('headline')]
                        if headlines:
                            response.say("Here is the latest market recap. " + " ".join(f"{h}." for h in headlines[:3]))
                            response.redirect('/call/incoming')
                            return Response(str(response), mimetype='application/xml')
                except Exception as e:
                    logger.error(f"Finnhub market news error: {e}")

            # Fallback to MarketWatch RSS
            try:
                rss = AnalysisClient()
                recap = rss.get_market_recap()
                response.say(recap)
            except Exception as e:
                logger.error(f"RSS market recap error: {e}")
                response.say("Market recap is currently unavailable. Please try again later.")

            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

