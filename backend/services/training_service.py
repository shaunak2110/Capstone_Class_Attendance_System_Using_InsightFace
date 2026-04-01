"""
Training Service Module

This module provides incremental training functionality for the face recognition model.
It handles adding new student embeddings to the model and persisting the updated weights.

Requirements: 6.4, 6.5, 10.3, 10.6, 12.2
"""

import numpy as np
from typing import List
import sys
import os

# Add parent directory to path to import FaceModel
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model.face_model import FaceModel


def incremental_train(face_model: FaceModel, prn: str, face_images: List[np.ndarray]) -> None:
    """
    Perform incremental training by adding new student embeddings to the face model.
    
    This function:
    1. Generates embeddings for all provided face images
    2. Adds the embeddings to the FaceModel using add_student()
    3. Persists the updated model weights to disk
    
    Args:
        face_model: The FaceModel instance to update
        prn: Permanent Registration Number of the student
        face_images: List of face images as numpy arrays (H, W, C) in RGB format
        
    Raises:
        ValueError: If face_images is empty or contains invalid images
        RuntimeError: If embedding generation or model saving fails
    """
    if not face_images:
        raise ValueError("At least one face image must be provided for training")
    
    if not prn or not isinstance(prn, str):
        raise ValueError("Valid PRN string must be provided")
    
    try:
        # Generate embeddings for all face images
        embeddings = []
        for idx, face_image in enumerate(face_images):
            if not isinstance(face_image, np.ndarray):
                raise ValueError(f"Face image at index {idx} is not a numpy array")
            
            if len(face_image.shape) != 3:
                raise ValueError(f"Face image at index {idx} has invalid shape {face_image.shape}, expected (H, W, C)")
            
            # Generate embedding for this face
            embedding = face_model.generate_embedding(face_image)
            embeddings.append(embedding)
        
        # Add all embeddings to the model for this student
        face_model.add_student(prn, embeddings)
        
        # Persist the updated model weights to disk
        face_model.save_model()
        
        print(f"Successfully trained model with {len(embeddings)} embeddings for student {prn}")
        
    except ValueError as e:
        # Re-raise validation errors
        raise ValueError(f"Training failed due to validation error: {e}")
    
    except Exception as e:
        # Wrap unexpected errors in RuntimeError
        raise RuntimeError(f"Training failed for student {prn}: {e}")
