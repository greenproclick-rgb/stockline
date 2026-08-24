from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import logging
from src.finnhub.data_processor import DataProcessor
from src.ivr.utils import map_t9_to_symbol
from src.ivr.news_narrator import NewsNarrator

logger = logging.getLogger(__name__)

class VoiceHandler:
    def __init__(self, call_manager, settings):
        self.call_manager = call_manager
        self.settings = settings
        self.app = Flask(__name__)
        self.finnhub_client = getattr(call_manager, 'finnhub_client', None)
        self._news_cache = {}
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
                gather = Gather(num_digits=1, action='/call/movers-menu', method='POST', timeout=5)
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
                    quote_text = DataProcessor.format_quote_for_voice(quote)
                    response.say(quote_text or f"{symbol} is trading at {price:.2f} dollars.")
                    gather = Gather(
                        num_digits=1,
                        action=f'/call/quote-options?symbol={symbol}',
                        method='POST',
                        timeout=15,
                    )
                    gather.say(
                        "Press 1 for the expanded quote. Press 2 for news headlines. "
                        "Press 3 for historical performance. Press star to go back."
                    )
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
            elif digit == '3':
                response.redirect(f'/call/historical-performance?symbol={symbol}')
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

            try:
                quote = self.finnhub_client.get_quote(symbol)
                financials = self.finnhub_client.get_basic_financials(symbol)
                target = self.finnhub_client.get_price_target(symbol)
                rec = self.finnhub_client.get_recommendation_trends(symbol)
                earnings = self.finnhub_client.get_earnings_summary(symbol)
            except Exception as e:
                logger.error(f"Stock info error for {symbol}: {e}")
                quote = None
                financials = None
                target = None
                rec = None
                earnings = None

            if not isinstance(financials, dict):
                financials = None
            if not isinstance(target, dict):
                target = None
            if not isinstance(rec, dict):
                rec = None
            if not isinstance(earnings, dict):
                earnings = None

            quote_text = DataProcessor.format_quote_for_voice(
                quote,
                financials=financials,
                price_target=target,
                recommendations=rec,
                earnings=earnings,
                include_extended=True,
            )
            if quote_text:
                response.say(quote_text)
            else:
                response.say(f"I could not retrieve detailed information for {symbol}.")

            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        # 2c. STOCK ANALYSIS / NEWS HEADLINES
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
                self._news_cache[symbol] = news or []
                briefing = NewsNarrator.build_briefing(news or [], symbol=symbol, max_items=3)
                index = max(int(request.args.get('index', 0)), 0)
                if briefing['headline_count'] and index < briefing['headline_count']:
                    response.say(briefing['headlines'][index])
                    gather = Gather(
                        num_digits=1,
                        action=f'/call/news-menu?symbol={symbol}&index={index}',
                        method='POST',
                        timeout=15,
                    )
                    gather.say(
                        "Press 1 to hear the article summary. Press 2 for the next headline. "
                        "Press star to return to the main menu."
                    )
                    response.append(gather)
                    return Response(str(response), mimetype='application/xml')
                elif briefing['headline_count']:
                    response.say(f"Those are the latest available headlines for {symbol}.")
                else:
                    response.say(f"No recent analysis found for {symbol}.")
            except Exception as e:
                logger.error(f"Stock analysis error for {symbol}: {e}")
                response.say(f"Analysis for {symbol} is currently unavailable.")

            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/news-menu', methods=['POST'])
        def news_menu():
            symbol = request.args.get('symbol', '').upper()
            index = max(int(request.args.get('index', 0)), 0)
            digit = request.form.get('Digits', '')
            response = VoiceResponse()

            if not symbol or not self.finnhub_client:
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            try:
                news = self._news_cache.get(symbol)
                if news is None:
                    news = self.finnhub_client.get_company_news(symbol) or []
                    self._news_cache[symbol] = news
                playlist = NewsNarrator.build_playlist(news or [])
                if not playlist or index >= len(playlist):
                    response.say("There are no more headlines right now.")
                    response.redirect('/call/incoming')
                    return Response(str(response), mimetype='application/xml')

                if digit == '1':
                    response.say(NewsNarrator.article_prompt(playlist[index]))
                    if index + 1 < len(playlist):
                        response.redirect(f'/call/stock-analysis?symbol={symbol}&index={index + 1}')
                    else:
                        response.redirect('/call/incoming')
                elif digit == '2':
                    if index + 1 < len(playlist):
                        response.redirect(f'/call/stock-analysis?symbol={symbol}&index={index + 1}')
                    else:
                        response.redirect('/call/incoming')
                else:
                    response.redirect('/call/incoming')
            except Exception as e:
                logger.error(f"News menu error for {symbol}: {e}")
                response.say("News playback is currently unavailable.")
                response.redirect('/call/incoming')

            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/historical-performance', methods=['POST'])
        def historical_performance():
            symbol = request.args.get('symbol', '').upper()
            response = VoiceResponse()

            if not symbol or not self.finnhub_client:
                response.say("Sorry, I could not retrieve historical performance.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            try:
                performance = self.finnhub_client.get_multi_period_performance(symbol)
                text = DataProcessor.format_historical_overview_for_voice(symbol, performance)
                if text:
                    response.say(text)
                else:
                    response.say(f"Historical performance for {symbol} is currently unavailable.")
            except Exception as e:
                logger.error(f"Historical performance error for {symbol}: {e}")
                response.say(f"Historical performance for {symbol} is currently unavailable.")

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

            # Validate input: only accept 1, 2, or 3
            if digit not in ['1', '2', '3']:
                logger.warning("ivr.movers.invalid_digit digit=%r", digit)
                response.say("Invalid selection. Returning to main menu.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            side_map = {'1': 'gainers', '2': 'losers', '3': 'actives'}
            side = side_map[digit]

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
