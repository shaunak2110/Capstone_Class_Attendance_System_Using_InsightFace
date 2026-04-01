"""
Recognition service for orchestrating face detection and recognition workflow.

This service coordinates the facial recognition process for attendance marking:
- Decodes base64 images to numpy arrays
- Processes images through the InferenceEngine
- Identifies students by matching face embeddings
- Retrieves student names from the database
- Manages unidentified faces with unique identifiers

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
"""

import base64
import numpy as np
import cv2
from typing import List, Dict, Tuple
import uuid
from database import execute_query


# In-memory storage for unidentified faces during attendance session
# Key: face_id (UUID), Value: face image (numpy array)
_unidentified_faces_cache: Dict[str, np.ndarray] = {}


def recognize_students(
    images: List[str],
    lecture_id: int,
    inference_engine
) -> Tuple[List[Dict], List[Dict]]:
    """
    Recognize students from a list of base64-encoded images.
    
    This function orchestrates the complete face recognition workflow:
    1. Decodes base64 images to numpy arrays
    2. Processes each image through InferenceEngine to detect faces and generate embeddings
    3. Identifies students by matching embeddings against enrolled students
    4. Queries Student_Master to retrieve student names by PRN
    5. Generates unique face_id (UUID) for each unidentified face
    6. Stores unidentified faces in temporary in-memory cache
    7. Returns lists of identified students and unidentified faces
    
    Args:
        images: List of base64-encoded image strings
        lecture_id: ID of the lecture for which attendance is being marked
        inference_engine: InferenceEngine instance for face detection and recognition
        
    Returns:
        Tuple of (identified_students, unidentified_faces) where:
            - identified_students: List of dicts with keys:
                - 'prn': Student's Permanent Registration Number
                - 'name': Student's full name from database
                - 'similarity': Cosine similarity score (0.0 to 1.0)
            - unidentified_faces: List of dicts with keys:
                - 'face_id': Unique UUID string for this face
                - 'image': Base64-encoded cropped face image
                
    Raises:
        ValueError: If images list is empty or contains invalid base64 data
        Exception: If database query fails or image processing fails
        
    Example:
        >>> engine = InferenceEngine(face_model)
        >>> identified, unidentified = recognize_students(
        ...     images=["base64_image_1", "base64_image_2"],
        ...     lecture_id=123,
        ...     inference_engine=engine
        ... )
        >>> print(f"Identified {len(identified)} students")
        >>> print(f"Found {len(unidentified)} unidentified faces")
    """
    if not images:
        raise ValueError("Images list cannot be empty")
    
    # Step 1: Decode base64 images to numpy arrays
    decoded_images = []
    for idx, img_base64 in enumerate(images):
        try:
            # Remove data URL prefix if present (e.g., "data:image/jpeg;base64,")
            if ',' in img_base64:
                img_base64 = img_base64.split(',', 1)[1]
            
            # Decode base64 to bytes
            img_bytes = base64.b64decode(img_base64)
            
            # Convert bytes to numpy array
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            
            # Decode image using OpenCV
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            if img is None:
                raise ValueError(f"Failed to decode image at index {idx}")
            
            decoded_images.append(img)
            
        except Exception as e:
            raise ValueError(f"Invalid base64 image data at index {idx}: {str(e)}")
    
    # Step 2 & 3: Process images and collect all detected faces and embeddings
    all_face_data = []
    for img in decoded_images:
        try:
            # Call InferenceEngine.process_image() for each image
            # Returns list of dicts with 'face_image' and 'embedding'
            face_data = inference_engine.process_image(img)
            all_face_data.extend(face_data)
        except ValueError as e:
            # No faces detected in this image - continue with other images
            continue
        except Exception as e:
            # Log error but continue processing other images
            print(f"Error processing image: {str(e)}")
            continue
    
    # Step 4: Call InferenceEngine.identify_students() to match faces
    identified_list, unidentified_face_images = inference_engine.identify_students(
        face_data=all_face_data,
        threshold=0.6
    )
    
    # Step 5: Query Student_Master for student names by PRN
    identified_students = []
    for student_info in identified_list:
        prn = student_info['prn']
        similarity = student_info['similarity']
        
        try:
            # Query database for student name
            query = "SELECT name FROM Student_Master WHERE prn = ?"
            results = execute_query(query, (prn,), fetch=True)
            
            if results and len(results) > 0:
                student_name = results[0].name
                identified_students.append({
                    'prn': prn,
                    'name': student_name,
                    'similarity': similarity
                })
            else:
                # PRN not found in database - treat as unidentified
                # This shouldn't happen if model is in sync with database
                print(f"Warning: PRN {prn} identified by model but not found in database")
                unidentified_face_images.append(student_info['face_image'])
                
        except Exception as e:
            print(f"Error querying student name for PRN {prn}: {str(e)}")
            # Treat as unidentified if database query fails
            unidentified_face_images.append(student_info['face_image'])
    
    # Step 6 & 7: Generate unique face_id (UUID) for each unidentified face
    # and store in temporary cache
    unidentified_faces = []
    for face_image in unidentified_face_images:
        # Generate unique UUID for this face
        face_id = str(uuid.uuid4())
        
        # Store face image in cache for later resolution
        _unidentified_faces_cache[face_id] = face_image
        
        # Convert face image to base64 for response
        try:
            # Ensure image is in correct format
            if face_image.dtype == np.float32 or face_image.dtype == np.float64:
                face_image_uint8 = (face_image * 255).astype(np.uint8)
            else:
                face_image_uint8 = face_image
            
            # Encode image to JPEG
            _, buffer = cv2.imencode('.jpg', face_image_uint8)
            face_base64 = base64.b64encode(buffer).decode('utf-8')
            
            unidentified_faces.append({
                'face_id': face_id,
                'image': face_base64
            })
        except Exception as e:
            print(f"Error encoding unidentified face: {str(e)}")
            continue
    
    return identified_students, unidentified_faces


def get_unidentified_face(face_id: str) -> np.ndarray:
    """
    Retrieve an unidentified face image from the temporary cache.
    
    Args:
        face_id: UUID string identifying the face
        
    Returns:
        Face image as numpy array
        
    Raises:
        KeyError: If face_id is not found in cache
    """
    if face_id not in _unidentified_faces_cache:
        raise KeyError(f"Face ID {face_id} not found in cache")
    
    return _unidentified_faces_cache[face_id]


def clear_unidentified_faces():
    """
    Clear all unidentified faces from the temporary cache.
    
    This should be called after attendance is finalized or when
    starting a new attendance marking session.
    """
    global _unidentified_faces_cache
    _unidentified_faces_cache.clear()


def remove_unidentified_face(face_id: str) -> bool:
    """
    Remove a specific unidentified face from the cache.
    
    Args:
        face_id: UUID string identifying the face
        
    Returns:
        True if face was removed, False if face_id was not found
    """
    if face_id in _unidentified_faces_cache:
        del _unidentified_faces_cache[face_id]
        return True
    return False
