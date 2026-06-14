# Stockline IVR - Quick Start Guide

## 5-Minute Setup

### 1. Clone Repository
```bash
git clone https://github.com/greenproclick-rgb/stockline.git
cd stockline
```

### 2. Get API Keys
- **Finnhub**: Get free API key from https://finnhub.io/register
- **Twilio**: Create account at https://www.twilio.com/try-twilio

### 3. Setup Environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 4. Run with Docker (Easiest)
```bash
docker-compose up
```

Or run locally:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

### 5. Test API
```bash
curl http://localhost:5000/api/health
curl http://localhost:5000/api/quote/AAPL
```

## Features

✅ **Voice Interface** - Call your Twilio number to get stock quotes
✅ **REST API** - Query stock data programmatically
✅ **Caching** - Redis-based caching for fast responses
✅ **Company Search** - Find stocks by company name
✅ **Price Targets** - Get analyst price targets
✅ **Containerized** - Docker ready for easy deployment

## Call Your IVR

1. Set Twilio webhook to: `https://your-domain/call/incoming`
2. Call your Twilio phone number
3. Follow voice prompts:
   - Press 1: Get stock quote
   - Press 2: Search company
   - Press 3: Market summary
   - Press 0: Hang up

## API Examples

### Get Quote
```bash
curl http://localhost:5000/api/quote/AAPL
```

### Search
```bash
curl "http://localhost:5000/api/search?q=apple"
```

### Voice Format
```bash
curl http://localhost:5000/api/quote/AAPL/voice
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed production deployment instructions.

## Troubleshooting

**Can't connect to API?**
- Make sure app is running: `python -m src.main`
- Check port 5000 is not blocked
- Verify .env file has correct API keys

**Voice calls not working?**
- Verify Twilio webhook URL is set correctly
- Check webhook URL is accessible (HTTPS required)
- Review Twilio call logs for errors

**Stock data not loading?**
- Verify Finnhub API key is valid
- Check API rate limits (60 req/min for free tier)
- Try different stock symbol

## What's Next?

1. Customize voice menus in `src/ivr/voice_handler.py`
2. Add more stock indicators to `src/finnhub/api_client.py`
3. Implement user authentication
4. Add SMS support alongside voice
5. Deploy to production (see DEPLOYMENT.md)

## Resources

- 📚 [Finnhub API Docs](https://finnhub.io/docs/api)
- 📞 [Twilio Voice Docs](https://www.twilio.com/docs/voice)
- 🐳 [Docker Docs](https://docs.docker.com/)
- 🍺 [Flask Docs](https://flask.palletsprojects.com/)
