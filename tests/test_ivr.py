"""
Unit tests for IVR system.
"""

import pytest
from unittest.mock import Mock, patch
from src.ivr.call_manager import CallManager
from src.finnhub.api_client import FinnhubClient

class TestCallManager:
    """Tests for CallManager."""
    
    @pytest.fixture
    def mock_finnhub(self):
        """Create mock Finnhub client."""
        return Mock(spec=FinnhubClient)
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        mock = Mock()
        mock.max_retries = 3
        mock.timeout_seconds = 30
        return mock
    
    def test_call_manager_initialization(self, mock_finnhub, mock_settings):
        """Test CallManager initialization."""
        manager = CallManager(mock_finnhub, mock_settings)
        assert manager is not None
        assert manager.finnhub_client == mock_finnhub
    
    def test_handle_incoming_call(self, mock_finnhub, mock_settings):
        """Test handling incoming call."""
        manager = CallManager(mock_finnhub, mock_settings)
        manager.handle_incoming_call('call123', '+1234567890', '+0987654321')
        assert 'call123' in manager.active_calls
    
    def test_end_call(self, mock_finnhub, mock_settings):
        """Test ending a call."""
        manager = CallManager(mock_finnhub, mock_settings)
        manager.handle_incoming_call('call123', '+1234567890', '+0987654321')
        manager._end_call('call123')
        assert 'call123' not in manager.active_calls
