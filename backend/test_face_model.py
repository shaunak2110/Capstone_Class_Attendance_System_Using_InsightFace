import pytest
import numpy as np
import torch
import os
import tempfile
from model.face_model import FaceModel


class TestFaceModel:
    """Unit tests for the FaceModel class"""
    
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
    
    def test_init_without_existing_model(self, temp_model_path):
        """Test initialization when model file doesn't exist"""
        # Remove the temp file so it doesn't exist
        if os.path.exists(temp_model_path):
            os.remove(temp_model_path)
        
        model = FaceModel(model_path=temp_model_path)
        
        assert model.model is not None
        assert model.prn_embeddings == {}
        assert model.model_path == temp_model_path
    
    def test_generate_embedding_shape(self, temp_model_path):
        """Test that generate_embedding produces 128-dimensional vectors"""
        model = FaceModel(model_path=temp_model_path)
        
        # Create a dummy face image (112x112x3 RGB)
        face_image = np.random.rand(112, 112, 3).astype(np.float32)
        
        embedding = model.generate_embedding(face_image)
        
        assert embedding.shape == (128,)
        assert isinstance(embedding, np.ndarray)
    
    def test_generate_embedding_normalization(self, temp_model_path):
        """Test that embeddings are L2-normalized (unit vectors)"""
        model = FaceModel(model_path=temp_model_path)
        
        face_image = np.random.rand(112, 112, 3).astype(np.float32)
        embedding = model.generate_embedding(face_image)
        
        # Check that the embedding is normalized (L2 norm should be ~1.0)
        norm = np.linalg.norm(embedding)
        assert abs(norm - 1.0) < 0.01, f"Embedding not normalized: norm={norm}"
    
    def test_add_student(self, temp_model_path):
        """Test adding a student with embeddings"""
        model = FaceModel(model_path=temp_model_path)
        
        prn = "PRN001"
        embeddings = [np.random.rand(128).astype(np.float32) for _ in range(3)]
        
        model.add_student(prn, embeddings)
        
        assert prn in model.prn_embeddings
        assert len(model.prn_embeddings[prn]) == 3
    
    def test_add_student_invalid_embedding_shape(self, temp_model_path):
        """Test that add_student rejects invalid embedding dimensions"""
        model = FaceModel(model_path=temp_model_path)
        
        prn = "PRN001"
        invalid_embeddings = [np.random.rand(64).astype(np.float32)]  # Wrong size
        
        with pytest.raises(ValueError, match="Expected embedding shape"):
            model.add_student(prn, invalid_embeddings)
    
    def test_add_student_empty_list(self, temp_model_path):
        """Test that add_student rejects empty embedding list"""
        model = FaceModel(model_path=temp_model_path)
        
        with pytest.raises(ValueError, match="At least one embedding"):
            model.add_student("PRN001", [])
    
    def test_identify_face_with_match(self, temp_model_path):
        """Test face identification when a match exists above threshold"""
        model = FaceModel(model_path=temp_model_path)
        
        # Create a known embedding
        known_embedding = np.random.rand(128).astype(np.float32)
        known_embedding = known_embedding / np.linalg.norm(known_embedding)  # Normalize
        
        model.add_student("PRN001", [known_embedding])
        
        # Try to identify with the same embedding (should match with similarity ~1.0)
        result = model.identify_face(known_embedding, threshold=0.6)
        
        assert result is not None
        prn, similarity = result
        assert prn == "PRN001"
        assert similarity > 0.99  # Should be very close to 1.0
    
    def test_identify_face_no_match(self, temp_model_path):
        """Test face identification when no match exists"""
        model = FaceModel(model_path=temp_model_path)
        
        # Add a student
        embedding1 = np.random.rand(128).astype(np.float32)
        embedding1 = embedding1 / np.linalg.norm(embedding1)
        model.add_student("PRN001", [embedding1])
        
        # Try to identify with a completely different embedding
        different_embedding = np.random.rand(128).astype(np.float32)
        different_embedding = different_embedding / np.linalg.norm(different_embedding)
        
        result = model.identify_face(different_embedding, threshold=0.99)
        
        # With high threshold and random embeddings, should not match
        assert result is None or result[1] < 0.99
    
    def test_identify_face_empty_database(self, temp_model_path):
        """Test identification when no students are enrolled"""
        model = FaceModel(model_path=temp_model_path)
        
        embedding = np.random.rand(128).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        
        result = model.identify_face(embedding)
        
        assert result is None
    
    def test_identify_face_threshold_behavior(self, temp_model_path):
        """Test that threshold parameter works correctly"""
        model = FaceModel(model_path=temp_model_path)
        
        embedding = np.random.rand(128).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        model.add_student("PRN001", [embedding])
        
        # With threshold 0.99, same embedding should match (accounting for floating point precision)
        result_high = model.identify_face(embedding, threshold=0.99)
        assert result_high is not None  # Same embedding should match
        
        # With threshold 0.0, any match should pass
        result_low = model.identify_face(embedding, threshold=0.0)
        assert result_low is not None
    
    def test_save_and_load_model(self, temp_model_path):
        """Test saving and loading model with PRN mappings"""
        # Create and populate a model
        model1 = FaceModel(model_path=temp_model_path)
        
        prn1 = "PRN001"
        prn2 = "PRN002"
        embeddings1 = [np.random.rand(128).astype(np.float32) for _ in range(2)]
        embeddings2 = [np.random.rand(128).astype(np.float32) for _ in range(3)]
        
        model1.add_student(prn1, embeddings1)
        model1.add_student(prn2, embeddings2)
        model1.save_model()
        
        # Load the model in a new instance
        model2 = FaceModel(model_path=temp_model_path)
        
        # Verify PRN mappings were loaded
        assert prn1 in model2.prn_embeddings
        assert prn2 in model2.prn_embeddings
        assert len(model2.prn_embeddings[prn1]) == 2
        assert len(model2.prn_embeddings[prn2]) == 3
    
    def test_get_enrolled_students(self, temp_model_path):
        """Test retrieving list of enrolled students"""
        model = FaceModel(model_path=temp_model_path)
        
        assert model.get_enrolled_students() == []
        
        embedding = np.random.rand(128).astype(np.float32)
        model.add_student("PRN001", [embedding])
        model.add_student("PRN002", [embedding])
        
        students = model.get_enrolled_students()
        assert len(students) == 2
        assert "PRN001" in students
        assert "PRN002" in students
    
    def test_get_student_embedding_count(self, temp_model_path):
        """Test getting embedding count for a student"""
        model = FaceModel(model_path=temp_model_path)
        
        embeddings = [np.random.rand(128).astype(np.float32) for _ in range(5)]
        model.add_student("PRN001", embeddings)
        
        assert model.get_student_embedding_count("PRN001") == 5
        assert model.get_student_embedding_count("PRN999") == 0
    
    def test_remove_student(self, temp_model_path):
        """Test removing a student from the model"""
        model = FaceModel(model_path=temp_model_path)
        
        embedding = np.random.rand(128).astype(np.float32)
        model.add_student("PRN001", [embedding])
        
        assert "PRN001" in model.prn_embeddings
        
        result = model.remove_student("PRN001")
        assert result is True
        assert "PRN001" not in model.prn_embeddings
        
        # Try removing non-existent student
        result = model.remove_student("PRN999")
        assert result is False
    
    def test_cosine_similarity_calculation(self, temp_model_path):
        """Test that cosine similarity is calculated correctly"""
        model = FaceModel(model_path=temp_model_path)
        
        # Create two embeddings with known similarity
        embedding1 = np.array([1.0, 0.0] + [0.0] * 126, dtype=np.float32)
        embedding2 = np.array([0.707, 0.707] + [0.0] * 126, dtype=np.float32)
        
        # Normalize
        embedding1 = embedding1 / np.linalg.norm(embedding1)
        embedding2 = embedding2 / np.linalg.norm(embedding2)
        
        model.add_student("PRN001", [embedding1])
        
        result = model.identify_face(embedding2, threshold=0.5)
        
        assert result is not None
        prn, similarity = result
        assert prn == "PRN001"
        # Cosine similarity should be approximately 0.707
        assert abs(similarity - 0.707) < 0.01
