"""
Inference adapter — wraps InsightFaceEngine with the interface expected by
recognition_service.py.

Old pipeline (removed):
  MTCNN → FaceEmbeddingNet (128-dim cosine)

New pipeline:
  InsightFaceEngine → buffalo_l ArcFace (512-dim Euclidean + ratio test)
"""

import base64
import numpy as np
from typing import Dict, List, Tuple

from model.insightface_engine import InsightFaceEngine


class InferenceEngine:
    """
    Adapter that exposes process_image() and identify_students() using
    InsightFaceEngine under the hood.

    recognition_service.py calls:
      face_data = engine.process_image(bgr_image)
      identified, unidentified = engine.identify_students(face_data, threshold)
    """

    def __init__(self, centroids: Dict[str, np.ndarray] | None = None) -> None:
        """
        Args:
            centroids: Optional pre-loaded {prn: centroid_embedding} dict.
                       Can be updated at runtime via set_centroids().
        """
        self._engine = InsightFaceEngine()
        self._centroids: Dict[str, np.ndarray] = centroids or {}

    def set_centroids(self, centroids: Dict[str, np.ndarray]) -> None:
        """Replace the in-memory centroid index (called after enrollment)."""
        self._centroids = centroids

    def process_image(self, image_bgr: np.ndarray) -> List[Dict]:
        """
        Detect faces and generate embeddings for a single BGR image.

        Returns list of dicts:
          {
            "embedding": np.ndarray (512,),
            "crop_b64":  str  base64 JPEG of the face crop,
            "bbox":      [x1, y1, x2, y2],
            "score":     float,
          }

        Raises ValueError if no faces are detected.
        """
        results = self._engine.detect_and_embed(image_bgr)
        if not results:
            raise ValueError("No faces detected in image")
        return results

    def identify_students(
        self,
        face_data: List[Dict],
        threshold: float = InsightFaceEngine.DEFAULT_THRESHOLD,
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Match face embeddings against stored centroids.

        Args:
            face_data:  Output of process_image() — list of face dicts.
            threshold:  Euclidean distance threshold.

        Returns:
            identified:    [{"prn": str, "similarity": float, "crop_b64": str}, ...]
            unidentified:  [{"crop_b64": str, "bbox": list}, ...]
        """
        identified = []
        unidentified = []

        for face in face_data:
            emb = face["embedding"]
            result = self._engine.identify(emb, self._centroids, threshold)
            if result is not None:
                prn, similarity = result
                identified.append({
                    "prn": prn,
                    "similarity": similarity,
                    "crop_b64": face["crop_b64"],
                })
            else:
                unidentified.append({
                    "crop_b64": face["crop_b64"],
                    "bbox": face["bbox"],
                })

        return identified, unidentified
