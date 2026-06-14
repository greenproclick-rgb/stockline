"""
Main entry point for the Stockline IVR system.
"""

import os
from dotenv import load_dotenv
from src.ivr.call_manager import CallManager
from src.finnhub.api_client import FinnhubClient
from config.settings import Settings

# Load environment variables
load_dotenv()

def initialize_system():
    """Initialize the IVR system components."""
    settings = Settings()
    finnhub_client = FinnhubClient(api_key=os.getenv('FINNHUB_API_KEY'))
    call_manager = CallManager(finnhub_client, settings)
    return call_manager, settings

def main():
    """Main function to start the IVR system."""
    try:
        call_manager, settings = initialize_system()
        print(f"Stockline IVR System started in {settings.environment} mode")
        print("Listening for incoming calls...")
        
        # Start the call manager
        call_manager.start()
        
    except Exception as e:
        print(f"Error starting IVR system: {e}")
        raise

if __name__ == "__main__":
    main()
