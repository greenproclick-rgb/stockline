# Stockline IVR System

An Interactive Voice Response (IVR) system that connects with Finnhub API to provide real-time stock information over voice.

## Features

- Real-time stock quotes via voice interface
- Voice-friendly quote narration with day change, percent change, and trend description
- Expanded quote details including 52-week range, P/E ratio, analyst ratings, price target, RSI, and earnings hook when available
- Historical performance narration for the last week, month, and quarter
- In-memory watchlist and portfolio models ready for future movers and rankings
- Stock and market news headline narration with article drill-down metadata for future audio controls
- Integration with Finnhub API
- Interactive voice response system
- Stock data retrieval and voice synthesis

## Project Structure

```
stockline/
├── src/
│   ├── ivr/
│   │   ├── voice_handler.py
│   │   ├── call_manager.py
│   │   └── menu_system.py
│   ├── finnhub/
│   │   ├── api_client.py
│   │   ├── data_processor.py
│   │   └── cache.py
│   ├── tts/
│   │   └── text_to_speech.py
│   ├── stt/
│   │   └── speech_to_text.py
│   └── main.py
├── config/
│   ├── settings.py
│   └── constants.py
├── tests/
│   └── test_ivr.py
├── requirements.txt
├── .env.example
└── docker-compose.yml
```

## Getting Started

### Prerequisites

- Python 3.9+
- Finnhub API key
- Twilio account (for voice handling)

### Installation

1. Clone the repository
2. Create virtual environment: `python -m venv venv`
3. Activate: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Configure `.env` with API keys

### Usage

```bash
python src/main.py
```

### MVP entry points

- Voice quote flow: `POST /call/get-quote?symbol=AAPL`
- Voice expanded quote: `POST /call/stock-info?symbol=AAPL`
- Voice historical narration: `POST /call/historical-performance?symbol=AAPL`
- Voice news narration: `POST /call/stock-analysis?symbol=AAPL`
- API historical narration: `GET /api/history/AAPL/voice`
- API earnings hook: `GET /api/earnings/AAPL`
- API watchlists: `GET|POST|DELETE /api/watchlists/<owner_id>/<name>` with `WATCHLIST_API_TOKEN` set and `X-Stockline-Token` / `X-Stockline-Owner` headers
- API portfolios: `GET|POST|DELETE /api/portfolios/<owner_id>/<name>` with `WATCHLIST_API_TOKEN` set and `X-Stockline-Token` / `X-Stockline-Owner` headers

## Configuration

See `.env.example` for required environment variables.

## License

MIT
