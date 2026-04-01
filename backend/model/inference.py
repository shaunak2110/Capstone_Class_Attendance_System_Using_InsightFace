import numpy as np
import cv2
from typing import List, Dict, Tuple, Optional
from facenet_pytorch import MTCNN
import torch
from PIL import Image


class InferenceEngine:
    """
    Inference engine for face detection and recognition.
    
    This class handles:
    - Face detection in images using MTCNN
    - Face embedding generation via FaceModel
    - Student identification by matching embeddings
    - Extraction of unidentified faces
    """
    
    def __init__(self, face_model):
        """
        Initialize the InferenceEngine with a FaceModel instance.
        
        Args:
            face_model: FaceModel instance for generating embeddings and identifying faces
        """
        self.face_model = face_model
        
        # Initialize MTCNN for face detection
        # MTCNN will detect faces and return aligned face crops
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.mtcnn = MTCNN(
            image_size=160,  # Output size for detected faces
            margin=0,
            min_face_size=20,
            thresholds=[0.6, 0.7, 0.7],  # Detection thresholds for P-Net, R-Net, O-Net
            factor=0.709,
            post_process=True,
            device=device,
            keep_all=True  # Detect all faces in the image
        )
    
    def detect_faces(self, image: np.ndarray) -> List[np.ndarray]:
        """
        Detect all faces in an image and return cropped face images.
        
        Args:
            image: Input image as numpy array (H, W, C) in RGB format
            
        Returns:
            List of cropped face images as numpy arrays
            
        Raises:
            ValueError: If no faces are detected in the image
        """
        # Convert numpy array to PIL Image for MTCNN
        if isinstance(image, np.ndarray):
            # Ensure image is in uint8 format
            if image.dtype == np.float32 or image.dtype == np.float64:
                image = (image * 255).astype(np.uint8)
            
            # Convert BGR to RGB if needed (OpenCV uses BGR)
            if len(image.shape) == 3 and image.shape[2] == 3:
                # Assume it might be BGR, convert to RGB
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = image
            
            pil_image = Image.fromarray(image_rgb)
        else:
            pil_image = image
        
        # Detect faces using MTCNN
        # Returns tensor of shape (num_faces, 3, 160, 160) or None if no faces
        faces_tensor = self.mtcnn(pil_image)
        
        if faces_tensor is None:
            raise ValueError("No faces detected in the image")
        
        # Convert tensor to list of numpy arrays
        faces = []
        if faces_tensor.dim() == 3:
            # Single face detected, add batch dimension
            faces_tensor = faces_tensor.unsqueeze(0)
        
        for face_tensor in faces_tensor:
            # Convert from (C, H, W) to (H, W, C)
            face_np = face_tensor.permute(1, 2, 0).cpu().numpy()
            faces.append(face_np)
        
        return faces
    
    def process_image(self, image: np.ndarray) -> List[Dict]:
        """
        Detect faces in an image and generate embeddings for each face.
        
        Args:
            image: Input image as numpy array (H, W, C) in RGB format
            
        Returns:
            List of dictionaries containing:
                - 'face_image': Cropped face image as numpy array
                - 'embedding': 128-dimensional embedding vector
                
        Raises:
            ValueError: If no faces are detected in the image
        """
        # Detect all faces in the image
        face_images = self.detect_faces(image)
        
        # Generate embeddings for each detected face
        results = []
        for face_image in face_images:
            # Generate embedding using the face model
            embedding = self.face_model.generate_embedding(face_image)
            
            results.append({
                'face_image': face_image,
                'embedding': embedding
            })
        
        return results
    
    def identify_students(
        self, 
        face_data: List[Dict],
        threshold: float = 0.6
    ) -> Tuple[List[Dict], List[np.ndarray]]:
        """
        Identify students from face embeddings and separate unidentified faces.
        
        Args:
            face_data: List of dictionaries containing 'face_image' and 'embedding'
            threshold: Minimum similarity score for identification (default: 0.6)
            
        Returns:
            Tuple of (identified_students, unidentified_faces) where:
                - identified_students: List of dicts with 'prn', 'similarity', 'face_image'
                - unidentified_faces: List of face images (numpy arrays) that couldn't be identified
        """
        identified_students = []
        unidentified_faces = []
        
        for face_info in face_data:
            embedding = face_info['embedding']
            face_image = face_info['face_image']
            
            # Try to identify the face
            result = self.face_model.identify_face(embedding, threshold=threshold)
            
            if result is not None:
                prn, similarity = result
                identified_students.append({
                    'prn': prn,
                    'similarity': float(similarity),
                    'face_image': face_image
                })
            else:
                # Face not identified, add to unidentified list
                unidentified_faces.append(face_image)
        
        return identified_students, unidentified_faces
