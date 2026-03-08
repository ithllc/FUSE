import pytest
from unittest.mock import MagicMock, patch
from src.vision.vision_state_capture import VisionStateCapture

@pytest.fixture
def mock_state_manager():
    return MagicMock()

@pytest.fixture
def vision_capture(mock_state_manager):
    return VisionStateCapture(project_id="test-project", state_manager=mock_state_manager)

def test_analyze_frame_returns_mermaid(vision_capture):
    # Mock the Gemini client response
    mock_response = MagicMock()
    mock_response.text = "graph TD\nA-->B"
    vision_capture.client.models.generate_content = MagicMock(return_value=mock_response)
    
    # Simulate a frame analysis
    import numpy as np
    dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    
    result = vision_capture._analyze_frame(dummy_frame)
    
    assert "graph TD" in result
    assert "A-->B" in result

def test_capture_updates_state(vision_capture, mock_state_manager):
    # Mock _analyze_frame to return a specific diagram
    vision_capture._analyze_frame = MagicMock(return_value="graph TD; X-->Y")
    
    # Mock cv2.VideoCapture to return one frame and then stop
    with patch('cv2.VideoCapture') as mock_cap:
        mock_instance = mock_cap.return_value
        mock_instance.isOpened.return_value = True
        mock_instance.read.side_effect = [(True, "frame1"), (False, None)]
        
        # Run a single iteration of capture (mocking the time/loop)
        with patch('time.sleep', return_value=None):
            vision_capture.capture_and_analyze(fps=100) # Fast interval for test
            
    mock_state_manager.update_architectural_state.assert_called_with("graph TD; X-->Y")
    mock_state_manager.log_event.assert_called()
