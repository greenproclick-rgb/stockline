"""
Speech-to-Text module for converting audio to text.
"""

import logging
from google.cloud import speech_v1
from typing import Optional

logger = logging.getLogger(__name__)

class SpeechToText:
    """Handles speech-to-text conversion using Google Cloud Speech-to-Text."""
    
    def __init__(self):
        """Initialize STT client."""
        self.client = speech_v1.SpeechClient()
    
    def transcribe(self, audio_content: bytes) -> Optional[str]:
        """Convert audio to text.
        
        Args:
            audio_content: Audio data in bytes
            
        Returns:
            Transcribed text or None if error
        """
        try:
            audio = speech_v1.RecognitionAudio(content=audio_content)
            config = speech_v1.RecognitionConfig(
                encoding=speech_v1.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code="en-US"
            )
            response = self.client.recognize(config=config, audio=audio)
            
            if response.results:
                return response.results[0].alternatives[0].transcript
            return None
        except Exception as e:
            logger.error(f"Error transcribing speech: {e}")
            return None
