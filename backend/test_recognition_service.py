"""
Unit tests for the recognition service.

Tests cover:
- Base64 image decoding
- Face detection and recognition workflow
- Student name retrieval from database
- Unidentified face handling with UUID generation
- Cache management for unidentified faces
"""

import pytest
import base64
import numpy as np
import cv2
from unittest.mock import Mock, patch, MagicMock
from services.recognition_service import (
    recognize_students,
    get_unidentified_face,
    clear_unidentified_faces,
    remove_unidentified_face,
    _unidentified_faces_cache
)


@pytest.fixture
def mock_inference_engine():
    """Create a mock InferenceEngine for testing."""
    engine = Mock()
    return engine


@pytest.fixture
def sample_base64_image():
    """Create a sample base64-encoded image for testing."""
    # Create a simple 100x100 RGB image
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :] = [100, 150, 200]  # Fill with a color
    
    # Encode to JPEG
    _, buffer = cv2.imencode('.jpg', img)
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    
    return img_base64


@pytest.fixture
def sample_face_image():
    """Create a sample face image as numpy array."""
    face = np.random.rand(160, 160, 3).astype(np.float32)
    return face


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the unidentified faces cache before each test."""
    clear_unidentified_faces()
    yield
    clear_unidentified_faces()


class TestRecognizeStudents:
    """Test suite for the recognize_students function."""
    
    def test_empty_images_list_raises_error(self, mock_inference_engine):
        """Test that empty images list raises ValueError."""
        with pytest.raises(ValueError, match="Images list cannot be empty"):
            recognize_students([], 123, mock_inference_engine)
    
    def test_invalid_base64_raises_error(self, mock_inference_engine):
        """Test that invalid base64 data raises ValueError."""
        invalid_images = ["not_valid_base64!!!"]
        
        with pytest.raises(ValueError, match="Invalid base64 image data"):
            recognize_students(invalid_images, 123, mock_inference_engine)
    
    def test_successful_image_decoding(self, sample_base64_image, mock_inference_engine):
        """Test that valid base64 images are decoded correctly."""
        # Mock process_image to return empty list (no faces)
        mock_inference_engine.process_image.return_value = []
        mock_inference_engine.identify_students.return_value = ([], [])
        
        identified, unidentified = recognize_students(
            [sample_base64_image],
            123,
            mock_inference_engine
        )
        
        # Should call process_image once
        assert mock_inference_engine.process_image.call_count == 1
        assert identified == []
        assert unidentified == []
    
    def test_data_url_prefix_handling(self, sample_base64_image, mock_inference_engine):
        """Test that data URL prefix is properly stripped."""
        # Add data URL prefix
        data_url = f"data:image/jpeg;base64,{sample_base64_image}"
        
        mock_inference_engine.process_image.return_value = []
        mock_inference_engine.identify_students.return_value = ([], [])
        
        identified, unidentified = recognize_students(
            [data_url],
            123,
            mock_inference_engine
        )
        
        # Should successfully decode despite prefix
        assert mock_inference_engine.process_image.call_count == 1
    
    def test_multiple_images_processing(self, sample_base64_image, mock_inference_engine):
        """Test that multiple images are all processed."""
        mock_inference_engine.process_image.return_value = []
        mock_inference_engine.identify_students.return_value = ([], [])
        
        # Process 3 images
        recognize_students(
            [sample_base64_image, sample_base64_image, sample_base64_image],
            123,
            mock_inference_engine
        )
        
        # Should call process_image 3 times
        assert mock_inference_engine.process_image.call_count == 3
    
    def test_no_faces_detected_continues_processing(self, sample_base64_image, mock_inference_engine):
        """Test that ValueError from no faces detected doesn't stop processing."""
        # First image has no faces, second has faces
        mock_inference_engine.process_image.side_effect = [
            ValueError("No faces detected"),
            [{'face_image': np.zeros((160, 160, 3)), 'embedding': np.zeros(128)}]
        ]
        mock_inference_engine.identify_students.return_value = ([], [])
        
        recognize_students(
            [sample_base64_image, sample_base64_image],
            123,
            mock_inference_engine
        )
        
        # Should call process_image twice despite first failure
        assert mock_inference_engine.process_image.call_count == 2
    
    @patch('services.recognition_service.execute_query')
    def test_identified_student_with_database_lookup(
        self,
        mock_execute_query,
        sample_base64_image,
        sample_face_image,
        mock_inference_engine
    ):
        """Test successful student identification with database name lookup."""
        # Mock face detection and embedding
        face_data = [{
            'face_image': sample_face_image,
            'embedding': np.random.rand(128)
        }]
        mock_inference_engine.process_image.return_value = face_data
        
        # Mock identification
        identified_list = [{
            'prn': 'PRN001',
            'similarity': 0.85,
            'face_image': sample_face_image
        }]
        mock_inference_engine.identify_students.return_value = (identified_list, [])
        
        # Mock database query
        mock_row = Mock()
        mock_row.name = "John Doe"
        mock_execute_query.return_value = [mock_row]
        
        identified, unidentified = recognize_students(
            [sample_base64_image],
            123,
            mock_inference_engine
        )
        
        # Verify results
        assert len(identified) == 1
        assert identified[0]['prn'] == 'PRN001'
        assert identified[0]['name'] == "John Doe"
        assert identified[0]['similarity'] == 0.85
        assert len(unidentified) == 0
        
        # Verify database was queried
        mock_execute_query.assert_called_once_with(
            "SELECT name FROM Student_Master WHERE prn = ?",
            ('PRN001',),
            fetch=True
        )
    
    @patch('services.recognition_service.execute_query')
    def test_multiple_identified_students(
        self,
        mock_execute_query,
        sample_base64_image,
        sample_face_image,
        mock_inference_engine
    ):
        """Test identification of multiple students."""
        # Mock multiple faces detected
        face_data = [
            {'face_image': sample_face_image, 'embedding': np.random.rand(128)},
            {'face_image': sample_face_image, 'embedding': np.random.rand(128)}
        ]
        mock_inference_engine.process_image.return_value = face_data
        
        # Mock identification of both
        identified_list = [
            {'prn': 'PRN001', 'similarity': 0.85, 'face_image': sample_face_image},
            {'prn': 'PRN002', 'similarity': 0.92, 'face_image': sample_face_image}
        ]
        mock_inference_engine.identify_students.return_value = (identified_list, [])
        
        # Mock database queries
        def mock_query(query, params, fetch):
            prn = params[0]
            mock_row = Mock()
            mock_row.name = f"Student {prn}"
            return [mock_row]
        
        mock_execute_query.side_effect = mock_query
        
        identified, unidentified = recognize_students(
            [sample_base64_image],
            123,
            mock_inference_engine
        )
        
        # Verify results
        assert len(identified) == 2
        assert identified[0]['prn'] == 'PRN001'
        assert identified[0]['name'] == "Student PRN001"
        assert identified[1]['prn'] == 'PRN002'
        assert identified[1]['name'] == "Student PRN002"
    
    @patch('services.recognition_service.execute_query')
    def test_prn_not_in_database_treated_as_unidentified(
        self,
        mock_execute_query,
        sample_base64_image,
        sample_face_image,
        mock_inference_engine
    ):
        """Test that PRN identified by model but not in database is treated as unidentified."""
        face_data = [{
            'face_image': sample_face_image,
            'embedding': np.random.rand(128)
        }]
        mock_inference_engine.process_image.return_value = face_data
        
        # Mock identification
        identified_list = [{
            'prn': 'PRN999',
            'similarity': 0.85,
            'face_image': sample_face_image
        }]
        mock_inference_engine.identify_students.return_value = (identified_list, [])
        
        # Mock database query returning no results
        mock_execute_query.return_value = []
        
        identified, unidentified = recognize_students(
            [sample_base64_image],
            123,
            mock_inference_engine
        )
        
        # Should be treated as unidentified
        assert len(identified) == 0
        assert len(unidentified) == 1
    
    def test_unidentified_faces_get_uuid_and_cached(
        self,
        sample_base64_image,
        sample_face_image,
        mock_inference_engine
    ):
        """Test that unidentified faces get UUID and are cached."""
        face_data = [{
            'face_image': sample_face_image,
            'embedding': np.random.rand(128)
        }]
        mock_inference_engine.process_image.return_value = face_data
        
        # Mock no identification
        mock_inference_engine.identify_students.return_value = ([], [sample_face_image])
        
        identified, unidentified = recognize_students(
            [sample_base64_image],
            123,
            mock_inference_engine
        )
        
        # Verify unidentified face structure
        assert len(unidentified) == 1
        assert 'face_id' in unidentified[0]
        assert 'image' in unidentified[0]
        
        # Verify UUID format (should be valid UUID)
        face_id = unidentified[0]['face_id']
        assert len(face_id) == 36  # UUID string length
        assert face_id.count('-') == 4  # UUID has 4 hyphens
        
        # Verify image is base64 encoded
        assert isinstance(unidentified[0]['image'], str)
        
        # Verify face is cached
        assert face_id in _unidentified_faces_cache
    
    def test_multiple_unidentified_faces(
        self,
        sample_base64_image,
        sample_face_image,
        mock_inference_engine
    ):
        """Test handling of multiple unidentified faces."""
        face_data = [
            {'face_image': sample_face_image, 'embedding': np.random.rand(128)},
            {'face_image': sample_face_image, 'embedding': np.random.rand(128)},
            {'face_image': sample_face_image, 'embedding': np.random.rand(128)}
        ]
        mock_inference_engine.process_image.return_value = face_data
        
        # Mock no identification for all faces
        unidentified_images = [sample_face_image, sample_face_image, sample_face_image]
        mock_inference_engine.identify_students.return_value = ([], unidentified_images)
        
        identified, unidentified = recognize_students(
            [sample_base64_image],
            123,
            mock_inference_engine
        )
        
        # Verify all faces are unidentified
        assert len(unidentified) == 3
        
        # Verify all have unique UUIDs
        face_ids = [face['face_id'] for face in unidentified]
        assert len(face_ids) == len(set(face_ids))  # All unique
        
        # Verify all are cached
        for face_id in face_ids:
            assert face_id in _unidentified_faces_cache


class TestCacheManagement:
    """Test suite for unidentified face cache management functions."""
    
    def test_get_unidentified_face_success(self, sample_face_image):
        """Test retrieving a face from cache."""
        face_id = "test-uuid-123"
        _unidentified_faces_cache[face_id] = sample_face_image
        
        retrieved_face = get_unidentified_face(face_id)
        
        assert np.array_equal(retrieved_face, sample_face_image)
    
    def test_get_unidentified_face_not_found(self):
        """Test that KeyError is raised for non-existent face_id."""
        with pytest.raises(KeyError, match="Face ID .* not found in cache"):
            get_unidentified_face("non-existent-uuid")
    
    def test_clear_unidentified_faces(self, sample_face_image):
        """Test clearing all faces from cache."""
        _unidentified_faces_cache["uuid1"] = sample_face_image
        _unidentified_faces_cache["uuid2"] = sample_face_image
        
        assert len(_unidentified_faces_cache) == 2
        
        clear_unidentified_faces()
        
        assert len(_unidentified_faces_cache) == 0
    
    def test_remove_unidentified_face_success(self, sample_face_image):
        """Test removing a specific face from cache."""
        face_id = "test-uuid-456"
        _unidentified_faces_cache[face_id] = sample_face_image
        
        result = remove_unidentified_face(face_id)
        
        assert result is True
        assert face_id not in _unidentified_faces_cache
    
    def test_remove_unidentified_face_not_found(self):
        """Test removing non-existent face returns False."""
        result = remove_unidentified_face("non-existent-uuid")
        
        assert result is False
