import pytest
from unittest.mock import MagicMock
from src.vision.vision_state_capture import VisionStateCapture

@pytest.fixture
def mock_state_manager():
    return MagicMock()

@pytest.fixture
def vision_capture(mock_state_manager):
    return VisionStateCapture(project_id="test-project", state_manager=mock_state_manager)

def test_process_received_frame_returns_mermaid(vision_capture):
    mock_response = MagicMock()
    mock_response.text = "graph TD\nA-->B"
    vision_capture.client.models.generate_content = MagicMock(return_value=mock_response)

    dummy_frame = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # fake JPEG bytes

    result = vision_capture.process_received_frame(dummy_frame)

    assert "graph TD" in result
    assert "A-->B" in result

def test_process_received_frame_updates_state(vision_capture, mock_state_manager):
    mock_response = MagicMock()
    mock_response.text = "graph TD; X-->Y"
    vision_capture.client.models.generate_content = MagicMock(return_value=mock_response)

    dummy_frame = b"\xff\xd8\xff\xe0" + b"\x00" * 100

    vision_capture.process_received_frame(dummy_frame)

    mock_state_manager.update_architectural_state.assert_called_with("graph TD; X-->Y")
    mock_state_manager.log_event.assert_called()

def test_process_received_frame_handles_error(vision_capture, mock_state_manager):
    vision_capture.client.models.generate_content = MagicMock(side_effect=Exception("API error"))

    result = vision_capture.process_received_frame(b"\xff\xd8\xff\xe0")

    assert result == ""
    mock_state_manager.update_architectural_state.assert_not_called()
