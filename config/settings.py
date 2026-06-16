"""
Application settings and configuration.
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Application settings."""
    
    # Environment
    environment = os.getenv('ENVIRONMENT', 'development')
    debug = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # Finnhub
    finnhub_api_key = os.getenv('FINNHUB_API_KEY')
    
    # Twilio
    twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')
    
    # Google Cloud
    google_cloud_project = os.getenv('GOOGLE_CLOUD_PROJECT')
    
    # Redis
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # IVR Settings
    max_retries = int(os.getenv('MAX_RETRIES', '3'))
    timeout_seconds = int(os.getenv('TIMEOUT_SECONDS', '30'))

    # FMP
    fmp_api_key = os.getenv('FMP_API_KEY')

    def __init__(self):
        """Validate required settings."""
        if not self.finnhub_api_key:
            raise ValueError("FINNHUB_API_KEY environment variable not set")
        if not self.twilio_account_sid or not self.twilio_auth_token:
            raise ValueError("Twilio credentials not set")
        if not self.fmp_api_key:
            raise ValueError("FMP_API_KEY environment variable not set")
