"""
Text-to-Speech module for converting text responses to audio.
"""

import logging
from google.cloud import texttospeech
from typing import Optional

logger = logging.getLogger(__name__)

class TextToSpeech:
    """Handles text-to-speech conversion using Google Cloud TTS."""
    
    def __init__(self):
        """Initialize TTS client."""
        self.client = texttospeech.TextToSpeechClient()
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Neural2-C"
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
    
    def synthesize(self, text: str) -> Optional[bytes]:
        """Convert text to speech audio.
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Audio content in bytes or None if error
        """
        try:
            request = texttospeech.SynthesizeSpeechRequest(
                input=texttospeech.SynthesisInput(text=text),
                voice=self.voice,
                audio_config=self.audio_config
            )
            response = self.client.synthesize_speech(request=request)
            return response.audio_content
        except Exception as e:
            logger.error(f"Error synthesizing speech: {e}")
            return None
