"""
InsightFace engine for face detection and 512-dim ArcFace embedding generation.

Uses the buffalo_l ONNX model pack (det_10g + w600k_r50) via the insightface
library. This replaces the old MTCNN + FaceEmbeddingNet pipeline entirely.

Embedding storage contract:
  - Each embedding is a float32 numpy array of shape (512,), L2-normalised.
  - Serialised to bytes:  embedding.astype(np.float32).tobytes()  → VARBINARY
  - Deserialised:         np.frombuffer(blob, dtype=np.float32)
"""

import base64
import logging
import os
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v


def _onnx_cuda_available() -> bool:
    """Return True only when the CUDA ONNX provider is actually available."""
    try:
        import onnxruntime as ort
    except Exception:
        return False
    if "CUDAExecutionProvider" not in set(ort.get_available_providers()):
        return False
    # On Windows, additionally verify the CUDA provider DLL is loadable
    import platform
    if platform.system() == 'Windows':
        provider_lib = os.path.join(
            os.path.dirname(ort.__file__), "capi", "onnxruntime_providers_cuda.dll"
        )
        if not os.path.exists(provider_lib):
            return False
        try:
            import ctypes
            ctypes.WinDLL(provider_lib)
            return True
        except OSError:
            return False
    # On Linux/Mac: if CUDAExecutionProvider is listed, trust it
    return True


def _resolve_model_root() -> str:
    """
    Resolve the parent directory of the buffalo_l/ model pack.

    InsightFace's FaceAnalysis(root=X) expects X to be the directory that
    CONTAINS buffalo_l/, not buffalo_l/ itself.

    Resolution order:
    1. MODEL_ROOT env var (must be the parent of buffalo_l/)
    2. Default: repo root = parent of backend/ = parent of parent of this file
    """
    model_root = os.getenv('MODEL_ROOT')
    if model_root:
        resolved = model_root
    else:
        # backend/model/insightface_engine.py → backend/model/ → backend/ → repo_root/
        this_file = os.path.abspath(__file__)
        model_dir = os.path.dirname(this_file)       # backend/model/
        backend_dir = os.path.dirname(model_dir)     # backend/
        resolved = os.path.dirname(backend_dir)      # repo_root/

    logger.info(f"[InsightFace] Resolved model root: {resolved}")

    if not os.path.isdir(resolved):
        raise RuntimeError(
            f"InsightFace model root directory not found at: {resolved}. "
            f"Set MODEL_ROOT env var to the parent directory of buffalo_l/, "
            f"or ensure buffalo_l/ is committed to the repository root."
        )
    return resolved


# ---------------------------------------------------------------------------
# InsightFaceEngine
# ---------------------------------------------------------------------------

class InsightFaceEngine:
    """
    Thin wrapper around insightface.app.FaceAnalysis (buffalo_l).

    Responsibilities:
      - Detect all faces in a BGR image.
      - Return 512-dim L2-normalised ArcFace embeddings for each face.
      - Identify a query embedding against a dict of stored centroids.
      - Serialise / deserialise embeddings for VARBINARY DB storage.
    """

    EMBEDDING_DIM = 512
    # Euclidean distance threshold calibrated for InsightFace buffalo_l.
    # Positive pairs cluster below ~0.63; negative pairs start above ~1.30.
    DEFAULT_THRESHOLD = 0.85

    def __init__(self) -> None:
        try:
            from insightface.app import FaceAnalysis  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "insightface is not installed. "
                "Run: pip install insightface onnxruntime"
            ) from exc

        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if _onnx_cuda_available()
            else ["CPUExecutionProvider"]
        )
        self._app = FaceAnalysis(name="buffalo_l", root=_resolve_model_root(), providers=providers)
        ctx_id = 0 if "CUDAExecutionProvider" in providers else -1
        self._app.prepare(ctx_id=ctx_id, det_size=(640, 640))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_and_embed(self, image_bgr: np.ndarray) -> List[Dict]:
        """
        Detect all faces in a BGR image and return embeddings.

        Returns a list of dicts, one per detected face:
          {
            "embedding": np.ndarray shape (512,) float32, L2-normalised,
            "bbox":      [x1, y1, x2, y2],
            "score":     float detection confidence,
            "crop_b64":  base64-encoded JPEG of the face crop (for unidentified cache),
          }
        """
        faces = self._app.get(image_bgr)
        results = []
        for face in faces:
            if not hasattr(face, "normed_embedding") or face.normed_embedding is None:
                continue
            emb = _normalize(np.asarray(face.normed_embedding, dtype=np.float32))
            x1, y1, x2, y2 = face.bbox.astype(int).tolist()
            # Clamp to image bounds
            h, w = image_bgr.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            crop = image_bgr[y1:y2, x1:x2]
            _, buf = cv2.imencode(".jpg", crop)
            crop_b64 = base64.b64encode(buf).decode("utf-8")
            results.append({
                "embedding": emb,
                "bbox": [x1, y1, x2, y2],
                "score": float(getattr(face, "det_score", 1.0)),
                "crop_b64": crop_b64,
            })
        return results

    def identify(
        self,
        embedding: np.ndarray,
        centroids: Dict[str, np.ndarray],
        threshold: float = DEFAULT_THRESHOLD,
    ) -> Optional[Tuple[str, float]]:
        """
        Compare a query embedding against stored per-student centroids.

        Uses Euclidean distance with a ratio test to reject ambiguous matches.

        Args:
            embedding:  Query 512-dim embedding.
            centroids:  {prn: centroid_embedding} loaded from Student_Embeddings.
            threshold:  Maximum Euclidean distance for a positive match.

        Returns:
            (prn, similarity_score) where similarity = 1 - (distance / threshold),
            or None if no confident match found.
        """
        if not centroids:
            return None

        distances: List[Tuple[float, str]] = []
        for prn, centroid in centroids.items():
            dist = float(np.linalg.norm(embedding - centroid))
            distances.append((dist, prn))

        distances.sort(key=lambda x: x[0])
        best_dist, best_prn = distances[0]

        if best_dist > threshold:
            return None

        # Ratio test: reject if 2nd-best is too close to best
        if len(distances) > 1:
            second_dist = distances[1][0]
            ratio = best_dist / (second_dist + 1e-6)
            margin = second_dist - best_dist
            if ratio > 0.85 or margin < 0.05:
                return None  # Ambiguous

        # Convert distance to a 0–1 similarity score for the frontend
        similarity = max(0.0, 1.0 - (best_dist / threshold))
        return best_prn, round(similarity, 4)

    # ------------------------------------------------------------------
    # Serialisation helpers (VARBINARY ↔ numpy)
    # ------------------------------------------------------------------

    @staticmethod
    def embedding_to_bytes(embedding: np.ndarray) -> bytes:
        """Serialise a float32 (512,) embedding to bytes for VARBINARY storage."""
        return embedding.astype(np.float32).tobytes()

    @staticmethod
    def bytes_to_embedding(blob: bytes) -> np.ndarray:
        """Deserialise VARBINARY bytes back to a float32 (512,) numpy array."""
        return np.frombuffer(blob, dtype=np.float32).copy()

    @staticmethod
    def compute_centroid(embeddings: List[np.ndarray]) -> np.ndarray:
        """Average a list of embeddings and L2-normalise the result."""
        stacked = np.stack(embeddings, axis=0)
        mean = np.mean(stacked, axis=0)
        return _normalize(mean)
