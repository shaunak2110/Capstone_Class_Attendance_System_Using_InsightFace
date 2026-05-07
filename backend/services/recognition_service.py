"""
Recognition service — orchestrates InsightFace-based attendance marking.

Flow:
  1. Load per-student centroid embeddings from Student_Embeddings table.
  2. Decode base64 classroom images → BGR numpy arrays.
  3. For each image: detect faces + generate 512-dim embeddings (InsightFaceEngine).
  4. Match each embedding against centroids → identified / unidentified split.
  5. Look up student names from Student_Master for identified PRNs.
  6. Cache unidentified face crops (base64) keyed by UUID for later resolution.
  7. Return (identified_students, unidentified_faces) to user.py.
"""

import base64
import uuid
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from database import execute_query
from model.insightface_engine import InsightFaceEngine


# ---------------------------------------------------------------------------
# In-memory cache for unidentified faces during an attendance session.
# Key:   face_id (UUID string)
# Value: base64-encoded JPEG crop string
# ---------------------------------------------------------------------------
_unidentified_cache: Dict[str, str] = {}


# ---------------------------------------------------------------------------
# Centroid loading
# ---------------------------------------------------------------------------

def load_centroids() -> Dict[str, np.ndarray]:
    """
    Load all student embeddings from Student_Embeddings and compute one
    centroid per PRN.

    Returns:
        {prn: centroid_embedding (512,) float32}
    """
    rows = execute_query(
        "SELECT prn, embedding FROM Student_Embeddings",
        fetch=True,
    )
    if not rows:
        return {}

    # Group raw embeddings by PRN
    grouped: Dict[str, List[np.ndarray]] = {}
    for row in rows:
        emb = InsightFaceEngine.bytes_to_embedding(bytes(row.embedding))
        grouped.setdefault(row.prn, []).append(emb)

    # Average + L2-normalise → one centroid per student
    centroids: Dict[str, np.ndarray] = {}
    for prn, embeddings in grouped.items():
        centroids[prn] = InsightFaceEngine.compute_centroid(embeddings)

    return centroids


# ---------------------------------------------------------------------------
# Main recognition entry point
# ---------------------------------------------------------------------------

def recognize_students(
    images: List[str],
    lecture_id: int,
    inference_engine,          # InferenceEngine instance injected by user.py
) -> Tuple[List[Dict], List[Dict]]:
    """
    Recognise students from a list of base64-encoded classroom images.

    Args:
        images:           List of base64 strings (with or without data-URL prefix).
        lecture_id:       ID of the current lecture (unused in matching, kept for
                          future per-lecture roster filtering).
        inference_engine: InferenceEngine instance (wraps InsightFaceEngine).

    Returns:
        identified_students: [{"prn": str, "name": str, "similarity": float}, ...]
        unidentified_faces:  [{"face_id": str, "image": str (base64 JPEG)}, ...]
    """
    if not images:
        raise ValueError("Images list cannot be empty")

    # ------------------------------------------------------------------
    # 1. Load centroids fresh from DB for this session
    # ------------------------------------------------------------------
    centroids = load_centroids()
    inference_engine.set_centroids(centroids)

    # ------------------------------------------------------------------
    # 2. Decode base64 images → BGR numpy arrays
    # ------------------------------------------------------------------
    bgr_images: List[np.ndarray] = []
    for idx, img_b64 in enumerate(images):
        try:
            if "," in img_b64:
                img_b64 = img_b64.split(",", 1)[1]
            img_bytes = base64.b64decode(img_b64)
            arr = np.frombuffer(img_bytes, dtype=np.uint8)
            bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if bgr is None:
                raise ValueError(f"cv2.imdecode returned None for image {idx}")
            bgr_images.append(bgr)
        except Exception as exc:
            raise ValueError(f"Invalid base64 image at index {idx}: {exc}") from exc

    # ------------------------------------------------------------------
    # 3. Detect + embed all faces across all images
    # ------------------------------------------------------------------
    all_face_data: List[Dict] = []
    for bgr in bgr_images:
        try:
            face_data = inference_engine.process_image(bgr)
            all_face_data.extend(face_data)
        except ValueError:
            # No faces in this image — skip silently
            continue
        except Exception as exc:
            print(f"[recognition_service] Error processing image: {exc}")
            continue

    # ------------------------------------------------------------------
    # 4. Match embeddings against centroids
    # ------------------------------------------------------------------
    identified_raw, unidentified_raw = inference_engine.identify_students(all_face_data)

    # ------------------------------------------------------------------
    # 5. Resolve PRNs → student names from Student_Master
    # ------------------------------------------------------------------
    # De-duplicate: keep highest-similarity match per PRN
    best_per_prn: Dict[str, Dict] = {}
    for match in identified_raw:
        prn = match["prn"]
        if prn not in best_per_prn or match["similarity"] > best_per_prn[prn]["similarity"]:
            best_per_prn[prn] = match

    identified_students: List[Dict] = []
    for prn, match in best_per_prn.items():
        try:
            rows = execute_query(
                "SELECT name FROM Student_Master WHERE prn = %s",
                (prn,),
                fetch=True,
            )
            name = rows[0].name if rows else "Unknown"
        except Exception:
            name = "Unknown"

        identified_students.append({
            "prn": prn,
            "name": name,
            "similarity": match["similarity"],
        })

    # ------------------------------------------------------------------
    # 6. Cache unidentified faces
    # ------------------------------------------------------------------
    unidentified_faces: List[Dict] = []
    for face in unidentified_raw:
        face_id = str(uuid.uuid4())
        crop_b64 = face["crop_b64"]
        _unidentified_cache[face_id] = crop_b64
        unidentified_faces.append({
            "face_id": face_id,
            "image": crop_b64,
        })

    return identified_students, unidentified_faces


# ---------------------------------------------------------------------------
# Cache helpers (called by user.py resolve-faces endpoint)
# ---------------------------------------------------------------------------

def get_unidentified_face(face_id: str) -> str:
    """
    Retrieve a cached unidentified face crop (base64 JPEG string).

    Raises:
        KeyError: If face_id is not in cache.
    """
    if face_id not in _unidentified_cache:
        raise KeyError(f"Face ID {face_id} not found in cache")
    return _unidentified_cache[face_id]


def remove_unidentified_face(face_id: str) -> bool:
    """Remove a face from the cache. Returns True if it existed."""
    return _unidentified_cache.pop(face_id, None) is not None


def clear_unidentified_faces() -> None:
    """Clear the entire cache (call at session start if needed)."""
    _unidentified_cache.clear()
