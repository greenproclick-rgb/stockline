# Stockline IVR System - Deployment Guide

## Prerequisites

- Python 3.9+
- Docker and Docker Compose (optional)
- Finnhub API key (free tier available at https://finnhub.io)
- Twilio account with phone number (signup at https://www.twilio.com)
- Google Cloud project with TTS/STT enabled (optional, for speech features)

## Local Development Setup

### 1. Clone and Setup

```bash
git clone https://github.com/greenproclick-rgb/stockline.git
cd stockline
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
FINNHUB_API_KEY=your_finnhub_key_here
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890
GOOGLE_CLOUD_PROJECT=your_project_id
ENVIRONMENT=development
DEBUG=True
```

### 4. Run Locally

```bash
python -m src.main
```

The application will start on `http://localhost:5000`

## Docker Deployment

### Build and Run

```bash
docker-compose up --build
```

This will:
- Start Redis container for caching
- Build and run the Stockline IVR container
- Expose the application on port 5000

### Run in Background

```bash
docker-compose up -d
```

### View Logs

```bash
docker-compose logs -f stockline-ivr
```

### Stop Services

```bash
docker-compose down
```

## Twilio Configuration

### 1. Set Webhook URL

In your Twilio Console:
1. Go to Phone Numbers > Active Numbers
2. Select your phone number
3. Set Voice & Fax webhook to:
   ```
   https://your-domain.com/call/incoming
   ```
4. Set Call Status Webhook to:
   ```
   https://your-domain.com/call/end
   ```

### 2. Test Your Setup

Call your Twilio number and follow the voice prompts.

## API Endpoints

### Health Check
```bash
curl http://localhost:5000/api/health
```

### Get Stock Quote
```bash
curl http://localhost:5000/api/quote/AAPL
```

### Search Stocks
```bash
curl http://localhost:5000/api/search?q=apple
```

### Get Company Profile
```bash
curl http://localhost:5000/api/profile/AAPL
```

### Get Quote in Voice Format
```bash
curl http://localhost:5000/api/quote/AAPL/voice
```

### Clear Cache
```bash
curl -X POST http://localhost:5000/api/cache/clear
```

## Production Deployment

### 1. Using Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 src.main:app
```

### 2. Using Cloud Platforms

#### Heroku
```bash
heroku create stockline-ivr
heroku config:set FINNHUB_API_KEY=your_key
heroku config:set TWILIO_ACCOUNT_SID=your_sid
heroku config:set TWILIO_AUTH_TOKEN=your_token
git push heroku main
```

#### Google Cloud Run
```bash
gcloud run deploy stockline-ivr --source . --platform managed
```

#### AWS
Create an EC2 instance or use Lambda with the Dockerfile.

### 3. Environment Variables for Production

```env
ENVIRONMENT=production
DEBUG=False
HOST=0.0.0.0
PORT=5000
REDIS_URL=redis://your-redis-host:6379/0
```

## SSL/TLS Setup

For Twilio webhooks, you need HTTPS. Use:
- **Let's Encrypt** with Certbot
- **Cloudflare** for SSL proxying
- **AWS ACM** with ALB

## Monitoring and Logging

### View Logs
```bash
tail -f logs/stockline.log
```

### Monitor Performance
```bash
curl http://localhost:5000/api/stats
```

## Troubleshooting

### Connection Issues
- Verify Finnhub API key is valid
- Check Twilio credentials in .env
- Ensure Redis is running (if using Docker)

### Call Routing Issues
- Verify webhook URL is accessible
- Check Twilio Call logs in dashboard
- Ensure phone number has voice capability

### API Errors
- Check stock symbol format (e.g., AAPL, not Apple)
- Verify Finnhub API rate limits (free tier: 60 requests/minute)
- Check cache status: `curl http://localhost:5000/api/cache/clear`

## Performance Optimization

### Caching
- Stock quotes are cached for 5 minutes by default
- Adjust `TTL_MINUTES` in cache.py as needed

### Database
- Use Redis for distributed deployments
- Monitor cache hit rates

### API Rate Limiting
- Implement rate limiting for production
- Monitor Finnhub API quotas

## Security Best Practices

1. Never commit `.env` file
2. Use environment variables for all secrets
3. Enable HTTPS/TLS for all connections
4. Validate and sanitize all input
5. Use Twilio request validation
6. Implement API authentication if needed

## Support

For issues or questions:
1. Check logs: `docker-compose logs stockline-ivr`
2. Review README.md for quick reference
3. Check Finnhub API documentation
4. Review Twilio webhook documentation
