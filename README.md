# Stockline IVR System

An Interactive Voice Response (IVR) system that connects with Finnhub API to provide real-time stock information over voice.

## Features

- Real-time stock quotes via voice interface
- Expanded quote narration with trend, 52-week range, P/E, analyst targets, RSI fallback, and earnings hooks
- Historical performance narration for the last week, month, and quarter
- In-memory watchlist and portfolio foundation with API endpoints for create/add/remove/list
- Stock and market headline narration with article playback placeholders for future controls
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

### MVP voice/API additions

- Voice quote flow now offers expanded quote details, historical performance, stock headlines, and earnings summaries.
- Market-wide headlines are available from the IVR main menu.
- Watchlist and portfolio foundations are exposed at `/api/collections/<watchlist|portfolio>/<name>`.

## Configuration

See `.env.example` for required environment variables.

## License

MIT
