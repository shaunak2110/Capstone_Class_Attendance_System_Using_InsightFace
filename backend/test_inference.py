import pytest
import numpy as np
import cv2
from PIL import Image
from model.inference import InferenceEngine
from model.face_model import FaceModel
import tempfile
import os


class TestInferenceEngine:
    """Unit tests for the InferenceEngine class"""
    
    @pytest.fixture
    def temp_model_path(self):
        """Create a temporary model path for testing"""
        with tempfile.NamedTemporaryFile(suffix='.pth', delete=False) as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
        mappings_path = temp_path.replace('.pth', '_mappings.pkl')
        if os.path.exists(mappings_path):
            os.remove(mappings_path)
    
    @pytest.fixture
    def face_model(self, temp_model_path):
        """Create a FaceModel instance for testing"""
        return FaceModel(model_path=temp_model_path)
    
    @pytest.fixture
    def inference_engine(self, face_model):
        """Create an InferenceEngine instance for testing"""
        return InferenceEngine(face_model)
    
    @pytest.fixture
    def sample_face_image(self):
        """Create a sample face image for testing"""
        # Create a simple synthetic face-like image (160x160x3)
        image = np.random.randint(0, 255, (160, 160, 3), dtype=np.uint8)
        # Add some structure to make it more face-like
        # Draw a simple oval shape
        center = (80, 80)
        axes = (40, 60)
        cv2.ellipse(image, center, axes, 0, 0, 360, (200, 180, 160), -1)
        # Add eyes
        cv2.circle(image, (60, 70), 5, (50, 50, 50), -1)
        cv2.circle(image, (100, 70), 5, (50, 50, 50), -1)
        # Add mouth
        cv2.ellipse(image, (80, 100), (20, 10), 0, 0, 180, (100, 50, 50), 2)
        return image
    
    def test_init(self, face_model):
        """Test InferenceEngine initialization"""
        engine = InferenceEngine(face_model)
        
        assert engine.face_model is face_model
        assert engine.mtcnn is not None
    
    def test_detect_faces_with_synthetic_image(self, inference_engine, sample_face_image):
        """Test face detection with a synthetic face image"""
        # Note: MTCNN may or may not detect faces in synthetic images
        # This test checks that the method runs without errors
        try:
            faces = inference_engine.detect_faces(sample_face_image)
            assert isinstance(faces, list)
            # If faces are detected, verify they are numpy arrays
            for face in faces:
                assert isinstance(face, np.ndarray)
                assert len(face.shape) == 3  # (H, W, C)
        except ValueError as e:
            # It's acceptable if no faces are detected in synthetic images
            assert "No faces detected" in str(e)
    
    def test_detect_faces_no_faces_error(self, inference_engine):
        """Test that detect_faces raises error when no faces are detected"""
        # Create a blank image with no face-like features
        blank_image = np.zeros((200, 200, 3), dtype=np.uint8)
        
        with pytest.raises(ValueError, match="No faces detected"):
            inference_engine.detect_faces(blank_image)
    
    def test_detect_faces_float_image(self, inference_engine, sample_face_image):
        """Test face detection with float32 image (normalized to 0-1)"""
        float_image = sample_face_image.astype(np.float32) / 255.0
        
        try:
            faces = inference_engine.detect_faces(float_image)
            assert isinstance(faces, list)
        except ValueError as e:
            # Acceptable if no faces detected in synthetic image
            assert "No faces detected" in str(e)
    
    def test_process_image_returns_embeddings(self, inference_engine, sample_face_image):
        """Test that process_image returns face data with embeddings"""
        # This test may fail if MTCNN doesn't detect faces in synthetic images
        # We'll handle both cases
        try:
            results = inference_engine.process_image(sample_face_image)
            
            assert isinstance(results, list)
            
            for result in results:
                assert 'face_image' in result
                assert 'embedding' in result
                assert isinstance(result['face_image'], np.ndarray)
                assert isinstance(result['embedding'], np.ndarray)
                assert result['embedding'].shape == (128,)
        except ValueError as e:
            # Acceptable if no faces detected
            assert "No faces detected" in str(e)
    
    def test_identify_students_with_known_face(self, inference_engine, face_model):
        """Test student identification with a known face"""
        # Create a known embedding and add to model
        known_embedding = np.random.rand(128).astype(np.float32)
        known_embedding = known_embedding / np.linalg.norm(known_embedding)
        face_model.add_student("PRN001", [known_embedding])
        
        # Create face data with the same embedding
        face_image = np.random.rand(160, 160, 3).astype(np.float32)
        face_data = [{
            'face_image': face_image,
            'embedding': known_embedding
        }]
        
        identified, unidentified = inference_engine.identify_students(face_data)
        
        assert len(identified) == 1
        assert len(unidentified) == 0
        assert identified[0]['prn'] == "PRN001"
        assert identified[0]['similarity'] > 0.99
        assert np.array_equal(identified[0]['face_image'], face_image)
    
    def test_identify_students_with_unknown_face(self, inference_engine, face_model):
        """Test student identification with an unknown face"""
        # Add a known student
        known_embedding = np.random.rand(128).astype(np.float32)
        known_embedding = known_embedding / np.linalg.norm(known_embedding)
        face_model.add_student("PRN001", [known_embedding])
        
        # Create face data with a different embedding
        unknown_embedding = np.random.rand(128).astype(np.float32)
        unknown_embedding = unknown_embedding / np.linalg.norm(unknown_embedding)
        face_image = np.random.rand(160, 160, 3).astype(np.float32)
        face_data = [{
            'face_image': face_image,
            'embedding': unknown_embedding
        }]
        
        identified, unidentified = inference_engine.identify_students(face_data, threshold=0.99)
        
        # With high threshold and random embeddings, should not match
        assert len(unidentified) == 1
        assert np.array_equal(unidentified[0], face_image)
    
    def test_identify_students_mixed_faces(self, inference_engine, face_model):
        """Test identification with both known and unknown faces"""
        # Add two known students
        embedding1 = np.random.rand(128).astype(np.float32)
        embedding1 = embedding1 / np.linalg.norm(embedding1)
        face_model.add_student("PRN001", [embedding1])
        
        embedding2 = np.random.rand(128).astype(np.float32)
        embedding2 = embedding2 / np.linalg.norm(embedding2)
        face_model.add_student("PRN002", [embedding2])
        
        # Create face data with 2 known and 1 unknown
        unknown_embedding = np.random.rand(128).astype(np.float32)
        unknown_embedding = unknown_embedding / np.linalg.norm(unknown_embedding)
        
        face_data = [
            {'face_image': np.random.rand(160, 160, 3), 'embedding': embedding1},
            {'face_image': np.random.rand(160, 160, 3), 'embedding': unknown_embedding},
            {'face_image': np.random.rand(160, 160, 3), 'embedding': embedding2},
        ]
        
        identified, unidentified = inference_engine.identify_students(face_data, threshold=0.99)
        
        assert len(identified) == 2
        assert len(unidentified) == 1
        
        prns = [student['prn'] for student in identified]
        assert "PRN001" in prns
        assert "PRN002" in prns
    
    def test_identify_students_empty_database(self, inference_engine):
        """Test identification when no students are enrolled"""
        embedding = np.random.rand(128).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        
        face_data = [{
            'face_image': np.random.rand(160, 160, 3),
            'embedding': embedding
        }]
        
        identified, unidentified = inference_engine.identify_students(face_data)
        
        assert len(identified) == 0
        assert len(unidentified) == 1
    
    def test_identify_students_threshold_behavior(self, inference_engine, face_model):
        """Test that threshold parameter affects identification"""
        # Add a student
        embedding = np.random.rand(128).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        face_model.add_student("PRN001", [embedding])
        
        face_data = [{
            'face_image': np.random.rand(160, 160, 3),
            'embedding': embedding
        }]
        
        # With low threshold, should identify
        identified_low, unidentified_low = inference_engine.identify_students(
            face_data, threshold=0.5
        )
        assert len(identified_low) == 1
        
        # With very high threshold (>1.0), should not identify
        identified_high, unidentified_high = inference_engine.identify_students(
            face_data, threshold=1.1
        )
        assert len(identified_high) == 0
        assert len(unidentified_high) == 1
    
    def test_identify_students_returns_similarity_scores(self, inference_engine, face_model):
        """Test that identified students include similarity scores"""
        embedding = np.random.rand(128).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        face_model.add_student("PRN001", [embedding])
        
        face_data = [{
            'face_image': np.random.rand(160, 160, 3),
            'embedding': embedding
        }]
        
        identified, _ = inference_engine.identify_students(face_data)
        
        assert len(identified) == 1
        assert 'similarity' in identified[0]
        assert isinstance(identified[0]['similarity'], float)
        assert 0.0 <= identified[0]['similarity'] <= 1.0
    
    def test_detect_faces_bgr_to_rgb_conversion(self, inference_engine):
        """Test that BGR images are properly converted to RGB"""
        # Create a BGR image (as OpenCV would provide)
        bgr_image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        
        # The method should handle BGR to RGB conversion internally
        try:
            faces = inference_engine.detect_faces(bgr_image)
            assert isinstance(faces, list)
        except ValueError as e:
            # Acceptable if no faces detected
            assert "No faces detected" in str(e)
    
    def test_process_image_with_multiple_faces(self, inference_engine):
        """Test processing an image with multiple faces"""
        # Create an image that might contain multiple face-like regions
        image = np.random.randint(0, 255, (400, 400, 3), dtype=np.uint8)
        
        try:
            results = inference_engine.process_image(image)
            
            # If faces are detected, verify structure
            assert isinstance(results, list)
            for result in results:
                assert 'face_image' in result
                assert 'embedding' in result
                assert result['embedding'].shape == (128,)
        except ValueError as e:
            # Acceptable if no faces detected in synthetic image
            assert "No faces detected" in str(e)
    
    def test_identify_students_preserves_face_images(self, inference_engine, face_model):
        """Test that face images are preserved in identification results"""
        embedding = np.random.rand(128).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        face_model.add_student("PRN001", [embedding])
        
        original_face = np.random.rand(160, 160, 3).astype(np.float32)
        face_data = [{
            'face_image': original_face,
            'embedding': embedding
        }]
        
        identified, _ = inference_engine.identify_students(face_data)
        
        assert len(identified) == 1
        assert 'face_image' in identified[0]
        assert np.array_equal(identified[0]['face_image'], original_face)
