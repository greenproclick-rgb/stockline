from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import logging
from src.finnhub.data_processor import DataProcessor
from src.ivr.utils import map_t9_to_symbol
from src.ivr.mvp_services import HistoricalPerformanceService, NewsService

logger = logging.getLogger(__name__)

class VoiceHandler:
    def __init__(self, call_manager, settings):
        self.call_manager = call_manager
        self.settings = settings
        self.app = Flask(__name__)
        self.finnhub_client = getattr(call_manager, 'finnhub_client', None)
        self.data_processor = DataProcessor()
        self.history_service = HistoricalPerformanceService(self.finnhub_client, self.data_processor)
        self.news_service = NewsService(self.finnhub_client)
        self.setup_routes()

    def setup_routes(self):
        # 1. MAIN MENU
        @self.app.route('/call/incoming', methods=['POST'])
        def handle_incoming_call():
            response = VoiceResponse()
            response.say("Welcome to Stockline.")
            gather = Gather(num_digits=1, action='/call/menu', method='POST', timeout=10)
            gather.say(
                "Press 1 for stock quotes. Press 2 for market headlines. "
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
            elif digit == '2':
                response.redirect('/call/market-headlines')
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
                    response.say(self.data_processor.format_quote_for_voice(quote))
                    gather = Gather(
                        num_digits=1,
                        action=f'/call/quote-options?symbol={symbol}',
                        method='POST',
                        timeout=15,
                    )
                    gather.say(
                        "Press 1 for expanded quote details. Press 2 for news headlines. "
                        "Press 3 for historical performance. Press 4 for earnings. Press star to go back."
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
                response.redirect(f'/call/historical-menu?symbol={symbol}')
            elif digit == '4':
                response.redirect(f'/call/earnings?symbol={symbol}')
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
                quote = self.finnhub_client.get_quote(symbol)
                summary = self.data_processor.format_quote_for_voice(quote)
                if summary:
                    parts.append(summary)
                if quote and quote.get('high') and quote.get('low'):
                    parts.append(f"Today's range is {quote['low']:.2f} to {quote['high']:.2f}.")

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

                rec = self.finnhub_client.get_recommendation_trends(symbol)
                if rec:
                    buy = (rec.get('buy') or 0) + (rec.get('strong_buy') or 0)
                    sell = (rec.get('sell') or 0) + (rec.get('strong_sell') or 0)
                    hold = rec.get('hold') or 0
                    total = buy + sell + hold
                    if total > 0:
                        sentiment = "bullish" if buy > max(hold, sell) else "bearish" if sell > max(buy, hold) else "mixed"
                        parts.append(f"Analyst ratings: {buy} buy, {hold} hold, {sell} sell. Overall sentiment is {sentiment}.")

                rsi = self.finnhub_client.get_rsi(symbol)
                if rsi and rsi.get('value') is not None:
                    parts.append(f"Relative strength index is {rsi['value']:.2f}.")
                elif parts:
                    parts.append("Relative strength index is not available right now.")

                earnings = self.finnhub_client.get_earnings(symbol)
                if earnings:
                    parts.append(self.data_processor.format_earnings_for_voice(symbol, earnings))
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
                news = self.news_service.get_company_headlines(symbol)
                if news:
                    response.say(f"Here are the latest headlines for {symbol}.")
                    for item in news[:3]:
                        headline = item.get('headline', '').strip()
                        if headline:
                            response.say(headline + ".")
                    gather = Gather(
                        num_digits=1,
                        action=f'/call/article-options?scope=stock&symbol={symbol}',
                        method='POST',
                        timeout=10,
                    )
                    gather.say("Press 1 to hear the first article summary. Press 2 for market headlines. Press star to return.")
                    response.append(gather)
                else:
                    response.say(f"No recent headlines found for {symbol}.")
            except Exception as e:
                logger.error(f"Stock analysis error for {symbol}: {e}")
                response.say(f"Headlines for {symbol} are currently unavailable.")

            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/historical-menu', methods=['POST'])
        def historical_menu():
            symbol = request.args.get('symbol', '').upper()
            response = VoiceResponse()

            if not symbol:
                response.say("Sorry, I could not retrieve historical performance.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            gather = Gather(
                num_digits=1,
                action=f'/call/historical-performance?symbol={symbol}',
                method='POST',
                timeout=10,
            )
            gather.say("Press 1 for the last week. Press 2 for the last month. Press 3 for the last quarter.")
            response.append(gather)
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/historical-performance', methods=['POST'])
        def historical_performance():
            symbol = request.args.get('symbol', '').upper()
            digit = request.form.get('Digits', '')
            response = VoiceResponse()

            period = {'1': 'week', '2': 'month', '3': 'quarter'}.get(digit)
            summary = self.history_service.get_summary(symbol, period) if period else None

            if summary:
                response.say(summary)
            else:
                response.say(f"Historical performance for {symbol or 'that symbol'} is not available right now.")

            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/earnings', methods=['POST'])
        def earnings():
            symbol = request.args.get('symbol', '').upper()
            response = VoiceResponse()

            if not symbol or not self.finnhub_client:
                response.say("Sorry, I could not retrieve earnings information.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            earnings_data = self.finnhub_client.get_earnings(symbol)
            response.say(self.data_processor.format_earnings_for_voice(symbol, earnings_data))
            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/article-options', methods=['POST'])
        def article_options():
            scope = request.args.get('scope', 'stock')
            symbol = request.args.get('symbol', '').upper()
            digit = request.form.get('Digits', '')
            response = VoiceResponse()

            if digit == '1':
                target = f'/call/article-playback?scope={scope}'
                if symbol:
                    target += f'&symbol={symbol}'
                response.redirect(target)
            elif digit == '2':
                response.redirect('/call/market-headlines')
            else:
                response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')

        @self.app.route('/call/article-playback', methods=['POST'])
        def article_playback():
            scope = request.args.get('scope', 'stock')
            symbol = request.args.get('symbol', '').upper()
            response = VoiceResponse()

            article = self.news_service.get_article(scope, symbol=symbol, index=0)
            if not article:
                response.say("Article playback is not available right now.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            response.say(article.get('headline', 'Headline unavailable'))
            summary = article.get('summary', '').strip()
            if summary:
                response.say(summary)
            response.say(
                "More article options are coming soon. "
                "Future controls will support play, pause, skip, rewind, and playback speed changes."
            )
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

        @self.app.route('/call/market-headlines', methods=['POST'])
        def market_headlines():
            response = VoiceResponse()

            if not self.finnhub_client:
                response.say("Market headlines are currently unavailable.")
                response.redirect('/call/incoming')
                return Response(str(response), mimetype='application/xml')

            headlines = self.news_service.get_market_headlines()
            if headlines:
                response.say("Here are the main market headlines.")
                for item in headlines[:3]:
                    headline = item.get('headline', '').strip()
                    if headline:
                        response.say(headline + ".")
                gather = Gather(
                    num_digits=1,
                    action='/call/article-options?scope=market',
                    method='POST',
                    timeout=10,
                )
                gather.say("Press 1 to hear the first article summary. Press star to return.")
                response.append(gather)
            else:
                response.say("Market headlines are currently unavailable.")

            response.redirect('/call/incoming')
            return Response(str(response), mimetype='application/xml')
