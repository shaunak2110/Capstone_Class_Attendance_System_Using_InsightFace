"""
Unit tests for the training service module.

Tests the incremental_train() function for:
- Successful training with valid inputs
- Error handling for invalid inputs
- Model persistence after training
"""

import pytest
import numpy as np
import os
import tempfile
from services.training_service import incremental_train
from model.face_model import FaceModel


class TestTrainingService:
    """Test suite for training service functionality"""
    
    @pytest.fixture
    def temp_model_path(self):
        """Create a temporary model file path for testing"""
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
    def sample_face_images(self):
        """Generate sample face images for testing"""
        # Create 3 sample face images (160x160x3 RGB)
        images = []
        for i in range(3):
            # Create random face image
            img = np.random.rand(160, 160, 3).astype(np.float32)
            images.append(img)
        return images
    
    def test_incremental_train_success(self, face_model, sample_face_images):
        """Test successful incremental training with valid inputs"""
        prn = "TEST001"
        
        # Perform incremental training
        incremental_train(face_model, prn, sample_face_images)
        
        # Verify student was added to model
        assert prn in face_model.get_enrolled_students()
        
        # Verify correct number of embeddings were stored
        assert face_model.get_student_embedding_count(prn) == len(sample_face_images)
    
    def test_incremental_train_empty_images(self, face_model):
        """Test that training fails with empty image list"""
        prn = "TEST002"
        
        with pytest.raises(ValueError, match="At least one face image must be provided"):
            incremental_train(face_model, prn, [])
    
    def test_incremental_train_invalid_prn(self, face_model, sample_face_images):
        """Test that training fails with invalid PRN"""
        with pytest.raises(ValueError, match="Valid PRN string must be provided"):
            incremental_train(face_model, "", sample_face_images)
        
        with pytest.raises(ValueError, match="Valid PRN string must be provided"):
            incremental_train(face_model, None, sample_face_images)
    
    def test_incremental_train_invalid_image_type(self, face_model):
        """Test that training fails with non-numpy array images"""
        prn = "TEST003"
        invalid_images = ["not_an_array", [1, 2, 3]]
        
        with pytest.raises(ValueError, match="not a numpy array"):
            incremental_train(face_model, prn, invalid_images)
    
    def test_incremental_train_invalid_image_shape(self, face_model):
        """Test that training fails with invalid image dimensions"""
        prn = "TEST004"
        # Create image with wrong shape (2D instead of 3D)
        invalid_images = [np.random.rand(160, 160)]
        
        with pytest.raises(ValueError, match="invalid shape"):
            incremental_train(face_model, prn, invalid_images)
    
    def test_incremental_train_model_persistence(self, face_model, sample_face_images, temp_model_path):
        """Test that model weights are persisted after training"""
        prn = "TEST005"
        
        # Perform training
        incremental_train(face_model, prn, sample_face_images)
        
        # Verify model file was created/updated
        assert os.path.exists(temp_model_path)
        
        # Load a new model instance and verify student is present
        new_model = FaceModel(model_path=temp_model_path)
        assert prn in new_model.get_enrolled_students()
        assert new_model.get_student_embedding_count(prn) == len(sample_face_images)
    
    def test_incremental_train_multiple_students(self, face_model, sample_face_images):
        """Test training multiple students sequentially"""
        prn1 = "TEST006"
        prn2 = "TEST007"
        
        # Train first student
        incremental_train(face_model, prn1, sample_face_images[:2])
        
        # Train second student
        incremental_train(face_model, prn2, sample_face_images)
        
        # Verify both students are enrolled
        enrolled = face_model.get_enrolled_students()
        assert prn1 in enrolled
        assert prn2 in enrolled
        
        # Verify correct embedding counts
        assert face_model.get_student_embedding_count(prn1) == 2
        assert face_model.get_student_embedding_count(prn2) == 3
    
    def test_incremental_train_preserves_existing_students(self, face_model, sample_face_images):
        """Test that training new student preserves existing student embeddings"""
        prn1 = "TEST008"
        prn2 = "TEST009"
        
        # Train first student
        incremental_train(face_model, prn1, sample_face_images[:2])
        count1_before = face_model.get_student_embedding_count(prn1)
        
        # Train second student
        incremental_train(face_model, prn2, sample_face_images)
        
        # Verify first student's embeddings are preserved
        assert face_model.get_student_embedding_count(prn1) == count1_before
        assert prn1 in face_model.get_enrolled_students()
    
    def test_incremental_train_with_single_image(self, face_model):
        """Test training with a single face image"""
        prn = "TEST010"
        single_image = [np.random.rand(160, 160, 3).astype(np.float32)]
        
        # Should succeed with just one image
        incremental_train(face_model, prn, single_image)
        
        assert prn in face_model.get_enrolled_students()
        assert face_model.get_student_embedding_count(prn) == 1
    
    def test_incremental_train_with_25_images(self, face_model):
        """Test training with 25 images (standard enrollment count)"""
        prn = "TEST011"
        images = [np.random.rand(160, 160, 3).astype(np.float32) for _ in range(25)]
        
        # Should succeed with 25 images
        incremental_train(face_model, prn, images)
        
        assert prn in face_model.get_enrolled_students()
        assert face_model.get_student_embedding_count(prn) == 25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
