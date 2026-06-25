from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import logging
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
            gather.say(
                "Press 1 for stock quotes. Press 2 for voice search. "
                "Press 3 for market movers. Press 4 for market recap. "
                "Press star at any time to return here."
            )
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
                gather.say("For top gainers, press 1. For top losers, press 2. For most active, press 3.")
                response.append(gather)
            elif digit == '4':
                response.redirect('/call/market-recap')
            else:
                response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 2. QUOTE FLOW — Finnhub-backed
        @self.app.route('/call/get-quote', methods=['POST'])
        def get_stock_quote():
            digits = request.form.get('Digits', '')
            raw_symbol = request.args.get('symbol') or map_t9_to_symbol(digits)

            if not raw_symbol:
                response = VoiceResponse()
                response.say("I could not understand that symbol.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            symbol = raw_symbol.upper()
            response = VoiceResponse()

            if not self.finnhub_client:
                logger.error("Finnhub client is not available in VoiceHandler.")
                response.say("Internal configuration error.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            try:
                quote = self.finnhub_client.get_quote(symbol)
                price = quote.get('current_price') if quote else None
                if not price:
                    response.say(f"I'm sorry, I couldn't find a quote for {symbol}.")
                    response.redirect('/call/incoming')
                else:
                    response.say(f"{symbol} is trading at {price:.2f} dollars.")
                    gather = Gather(
                        num_digits=1,
                        action=f'/call/quote-options?symbol={symbol}',
                        method='POST',
                        timeout=15,
                    )
                    gather.say("Press 1 for full stock information. Press 2 for analysis. Press star to go back.")
                    response.append(gather)
            except Exception as e:
                logger.error(f"Finnhub quote error for {symbol}: {e}")
                response.say("Error reaching the quote service.")
                response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 2a. QUOTE SUBMENU
        @self.app.route('/call/quote-options', methods=['POST'])
        def quote_options():
            digit = request.form.get('Digits', '')
            symbol = request.args.get('symbol', '').upper()
            response = VoiceResponse()
            if digit == '1':
                response.redirect(f'/call/stock-info?symbol={symbol}')
            elif digit == '2':
                response.redirect(f'/call/stock-analysis?symbol={symbol}')
            else:
                response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 2b. FULL STOCK INFORMATION
        @self.app.route('/call/stock-info', methods=['POST'])
        def stock_info():
            symbol = request.args.get('symbol', '').upper()
            response = VoiceResponse()

            if not symbol or not self.finnhub_client:
                response.say("Sorry, I could not retrieve stock information.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            parts = []
            try:
                # Current quote with intraday range
                quote = self.finnhub_client.get_quote(symbol)
                if quote and quote.get('current_price'):
                    parts.append(f"{symbol} is currently trading at {quote['current_price']:.2f} dollars.")
                    if quote.get('high') and quote.get('low'):
                        parts.append(f"Today's range is {quote['low']:.2f} to {quote['high']:.2f}.")

                # 52-week range and P/E ratio
                financials = self.finnhub_client.get_basic_financials(symbol)
                if financials:
                    if financials.get('52_week_high') and financials.get('52_week_low'):
                        parts.append(
                            f"52-week range: {financials['52_week_low']:.2f} to {financials['52_week_high']:.2f}."
                        )
                    if financials.get('pe_ratio'):
                        parts.append(f"Price to earnings ratio: {financials['pe_ratio']:.2f}.")

                # Analyst price target
                target = self.finnhub_client.get_price_target(symbol)
                if target and target.get('target_price'):
                    parts.append(f"Analyst consensus price target: {target['target_price']:.2f} dollars.")

                # Analyst ratings summary
                rec = self.finnhub_client.get_recommendation_trends(symbol)
                if rec:
                    buy = (rec.get('buy') or 0) + (rec.get('strong_buy') or 0)
                    sell = (rec.get('sell') or 0) + (rec.get('strong_sell') or 0)
                    hold = rec.get('hold') or 0
                    total = buy + sell + hold
                    if total > 0:
                        parts.append(f"Analyst ratings: {buy} buy, {hold} hold, {sell} sell.")
            except Exception as e:
                logger.error(f"Stock info error for {symbol}: {e}")

            if parts:
                for part in parts:
                    response.say(part)
            else:
                response.say(f"I could not retrieve detailed information for {symbol}.")

            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 2c. STOCK ANALYSIS (recent news)
        @self.app.route('/call/stock-analysis', methods=['POST'])
        def stock_analysis():
            symbol = request.args.get('symbol', '').upper()
            response = VoiceResponse()

            if not symbol or not self.finnhub_client:
                response.say("Sorry, I could not retrieve analysis.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            try:
                news = self.finnhub_client.get_company_news(symbol)
                if news:
                    response.say(f"Here is the latest analysis for {symbol}.")
                    for item in news[:3]:
                        headline = item.get('headline', '').strip()
                        if headline:
                            response.say(headline + ".")
                else:
                    response.say(f"No recent analysis found for {symbol}.")
            except Exception as e:
                logger.error(f"Stock analysis error for {symbol}: {e}")
                response.say(f"Analysis for {symbol} is currently unavailable.")

            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 3. MARKET MOVERS — Finnhub-backed
        @self.app.route('/call/movers-menu', methods=['POST'])
        def movers_menu():
            digit = request.form.get('Digits', '')
            response = VoiceResponse()

            if not self.finnhub_client:
                logger.error("Finnhub client is not available for movers.")
                response.say("Market movers are currently unavailable.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            side = 'gainers' if digit == '1' else 'losers' if digit == '2' else 'actives'
            try:
                movers = self.finnhub_client.get_market_movers(side)
                if movers:
                    response.say(f"Here are the top {len(movers)} {side}.")
                    for m in movers:
                        direction = "up" if m['pct_change'] >= 0 else "down"
                        response.say(
                            f"{m['symbol']}, {direction} {abs(m['pct_change']):.2f} percent."
                        )
                else:
                    response.say("Market movers data is currently unavailable.")
            except Exception as e:
                logger.error(f"Market movers error (side={side}): {e}")
                response.say("Market movers data is currently unavailable.")

            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 4. MARKET RECAP — Finnhub-backed
        @self.app.route('/call/market-recap', methods=['POST'])
        def market_recap():
            response = VoiceResponse()

            if not self.finnhub_client:
                logger.error("Finnhub client is not available for market recap.")
                response.say("Market recap is currently unavailable.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            try:
                news = self.finnhub_client.get_market_news()
                if news:
                    response.say("Here is today's market recap.")
                    for item in news[:3]:
                        headline = item.get('headline', '').strip()
                        if headline:
                            response.say(headline + ".")
                else:
                    response.say("Market recap is currently unavailable.")
            except Exception as e:
                logger.error(f"Market recap error: {e}")
                response.say("Market recap is currently unavailable.")

            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

