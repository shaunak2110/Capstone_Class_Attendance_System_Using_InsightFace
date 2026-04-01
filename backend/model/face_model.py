import torch
import torch.nn.functional as F
import numpy as np
import pickle
import os
from typing import List, Optional, Tuple, Dict
import sys

# Add parent directory to path to import FaceEmbeddingNet
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from face_model import FaceEmbeddingNet


class FaceModel:
    """
    Wrapper class for the facial recognition model that provides high-level
    functionality for embedding generation, student enrollment, and face identification.
    
    This class manages:
    - Loading and saving the trained neural network weights
    - Generating 128-dimensional face embeddings
    - Storing PRN-to-embedding mappings
    - Identifying faces using cosine similarity
    """
    
    def __init__(self, model_path: str = "trained_face_brain.pth"):
        """
        Initialize the FaceModel by loading trained weights and PRN-embedding mappings.
        
        Args:
            model_path: Path to the trained model weights file
        """
        self.model_path = model_path
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Initialize the neural network architecture
        self.model = FaceEmbeddingNet(embedding_dim=128)
        
        # Load trained weights if they exist
        if os.path.exists(model_path):
            try:
                checkpoint = torch.load(model_path, map_location=self.device)
                
                # Handle different checkpoint formats
                if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                    self.model.load_state_dict(checkpoint['model_state_dict'])
                    # Load PRN mappings if stored in checkpoint
                    self.prn_embeddings = checkpoint.get('prn_embeddings', {})
                else:
                    # Checkpoint is just the state dict
                    self.model.load_state_dict(checkpoint)
                    self.prn_embeddings = {}
                    
                print(f"Loaded model weights from {model_path}")
            except Exception as e:
                print(f"Warning: Could not load model weights: {e}")
                print("Initializing with random weights")
                self.prn_embeddings = {}
        else:
            print(f"Model file {model_path} not found. Initializing with random weights.")
            self.prn_embeddings = {}
        
        self.model.to(self.device)
        self.model.eval()  # Set to evaluation mode
        
        # Try to load PRN mappings from separate pickle file if not in checkpoint
        self.mappings_path = model_path.replace('.pth', '_mappings.pkl')
        if not self.prn_embeddings and os.path.exists(self.mappings_path):
            try:
                with open(self.mappings_path, 'rb') as f:
                    self.prn_embeddings = pickle.load(f)
                print(f"Loaded {len(self.prn_embeddings)} student mappings from {self.mappings_path}")
            except Exception as e:
                print(f"Warning: Could not load PRN mappings: {e}")
                self.prn_embeddings = {}
    
    def generate_embedding(self, face_image: np.ndarray) -> np.ndarray:
        """
        Generate a 128-dimensional embedding vector from a face image.
        
        Args:
            face_image: Face image as numpy array (H, W, C) in RGB format
            
        Returns:
            128-dimensional embedding vector as numpy array
        """
        # Ensure image is in correct format
        if face_image.dtype != np.float32:
            face_image = face_image.astype(np.float32) / 255.0
        
        # Convert from (H, W, C) to (C, H, W) for PyTorch
        if len(face_image.shape) == 3 and face_image.shape[2] == 3:
            face_image = np.transpose(face_image, (2, 0, 1))
        
        # Add batch dimension: (C, H, W) -> (1, C, H, W)
        face_tensor = torch.from_numpy(face_image).unsqueeze(0).to(self.device)
        
        # Generate embedding
        with torch.no_grad():
            embedding = self.model(face_tensor)
        
        # Convert to numpy and remove batch dimension
        embedding_np = embedding.cpu().numpy().squeeze()
        
        return embedding_np

    def add_student(self, prn: str, embeddings: List[np.ndarray]):
        """
        Add a new student's embeddings to the model's mapping.
        
        This stores multiple embeddings per student to improve recognition accuracy
        across different angles, lighting conditions, and expressions.
        
        Args:
            prn: Permanent Registration Number (unique student identifier)
            embeddings: List of 128-dimensional embedding vectors for the student
        """
        if not embeddings:
            raise ValueError("At least one embedding must be provided")
        
        # Validate embedding dimensions
        for emb in embeddings:
            if emb.shape != (128,):
                raise ValueError(f"Expected embedding shape (128,), got {emb.shape}")
        
        # Store embeddings for this PRN
        self.prn_embeddings[prn] = embeddings
        print(f"Added {len(embeddings)} embeddings for student {prn}")
    
    def identify_face(self, embedding: np.ndarray, threshold: float = 0.6) -> Optional[Tuple[str, float]]:
        """
        Identify a student by comparing a face embedding against stored embeddings
        using cosine similarity.
        
        Args:
            embedding: 128-dimensional embedding vector to identify
            threshold: Minimum cosine similarity score for a match (default: 0.6)
            
        Returns:
            Tuple of (prn, similarity_score) if a match is found above threshold,
            None otherwise
        """
        if embedding.shape != (128,):
            raise ValueError(f"Expected embedding shape (128,), got {embedding.shape}")
        
        if not self.prn_embeddings:
            return None
        
        best_match_prn = None
        best_similarity = threshold
        
        # Convert embedding to torch tensor for efficient computation
        embedding_tensor = torch.from_numpy(embedding).float()
        
        # Compare against all stored student embeddings
        for prn, stored_embeddings in self.prn_embeddings.items():
            for stored_emb in stored_embeddings:
                # Convert stored embedding to tensor
                stored_tensor = torch.from_numpy(stored_emb).float()
                
                # Compute cosine similarity
                # Since embeddings are already L2-normalized, dot product = cosine similarity
                similarity = torch.dot(embedding_tensor, stored_tensor).item()
                
                # Update best match if this is better
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match_prn = prn
        
        if best_match_prn is not None:
            return (best_match_prn, best_similarity)
        
        return None
    
    def save_model(self):
        """
        Save the model weights and PRN-embedding mappings to disk.
        
        This persists both the neural network weights and the student enrollment
        data to trained_face_brain.pth and a separate mappings pickle file.
        """
        try:
            # Save model weights and mappings together in checkpoint
            checkpoint = {
                'model_state_dict': self.model.state_dict(),
                'prn_embeddings': self.prn_embeddings
            }
            torch.save(checkpoint, self.model_path)
            print(f"Saved model weights to {self.model_path}")
            
            # Also save mappings separately as backup
            with open(self.mappings_path, 'wb') as f:
                pickle.dump(self.prn_embeddings, f)
            print(f"Saved {len(self.prn_embeddings)} student mappings to {self.mappings_path}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to save model: {e}")
    
    def get_enrolled_students(self) -> List[str]:
        """
        Get a list of all enrolled student PRNs.
        
        Returns:
            List of PRN strings
        """
        return list(self.prn_embeddings.keys())
    
    def get_student_embedding_count(self, prn: str) -> int:
        """
        Get the number of embeddings stored for a specific student.
        
        Args:
            prn: Student's Permanent Registration Number
            
        Returns:
            Number of embeddings stored for the student, or 0 if not found
        """
        return len(self.prn_embeddings.get(prn, []))
    
    def remove_student(self, prn: str) -> bool:
        """
        Remove a student's embeddings from the model.
        
        Args:
            prn: Student's Permanent Registration Number
            
        Returns:
            True if student was removed, False if student was not found
        """
        if prn in self.prn_embeddings:
            del self.prn_embeddings[prn]
            print(f"Removed student {prn} from model")
            return True
        return False
