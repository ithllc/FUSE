import pytest
import asyncio
from unittest.mock import MagicMock
from src.audio.gemini_live_stream_handler import GeminiLiveStreamHandler

@pytest.fixture
def mock_state_manager():
    return MagicMock()

@pytest.fixture
def audio_handler(mock_state_manager):
    return GeminiLiveStreamHandler(project_id="test-project", state_manager=mock_state_manager)

@pytest.mark.asyncio
async def test_process_simulated_command_registers_proxy(audio_handler, mock_state_manager):
    # Test assignment command
    command = "This coffee mug is our database cluster"
    response = await audio_handler.process_simulated_command(command)
    
    # Assert state manager was called correctly
    mock_state_manager.set_object_proxy.assert_called_with("coffee mug", "database cluster")
    mock_state_manager.log_event.assert_called()
    assert "coffee mug is now the database cluster" in response

@pytest.mark.asyncio
async def test_process_invalid_command(audio_handler):
    command = "What time is it?"
    response = await audio_handler.process_simulated_command(command)
    
    assert "Command not recognized" in response
