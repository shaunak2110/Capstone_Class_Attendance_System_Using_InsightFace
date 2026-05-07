"""
Recognition layer — BaseRecognizer ABC and RecognitionResult dataclass.

All concrete recognizer wrappers inherit from BaseRecognizer and must expose
a uniform interface regardless of the underlying model.

Interface contract:
  - build_gallery(pairs)  — enroll a set of (identity_label, face_crop) pairs
  - predict(face_crop, threshold, open_set) → RecognitionResult
  - name (property) → str
  - produces_embeddings (property) → bool  (False for LBPH)

Usage:
    from recognition import BaseRecognizer, RecognitionResult
    from recognition.insightface_recognizer import InsightFaceRecognizer
    from recognition.lbph_recognizer import LBPHRecognizer
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# RecognitionResult — uniform output for every recognizer
# ---------------------------------------------------------------------------

@dataclass
class RecognitionResult:
    """
    Standardised output for a single recognition prediction.

    Attributes:
        predicted_label: Predicted identity label, or "unknown" when the
                         recognizer rejects the probe in open-set mode.
                         None if the gallery is empty.
        similarity:      Similarity score in [0.0, 1.0].
                         Higher = more similar to the predicted identity.
                         For LBPH this is derived from the confidence distance
                         (lower distance → higher similarity).
        is_unknown:      True when the recognizer returned "unknown" (open-set
                         rejection). Always False in closed-set mode.
    """
    predicted_label: Optional[str]
    similarity: float
    is_unknown: bool = False

    def __post_init__(self) -> None:
        self.similarity = float(self.similarity)
        # Clamp to [0, 1]
        self.similarity = max(0.0, min(1.0, self.similarity))

    def is_valid(self) -> bool:
        """Return True if the result has a non-None label and valid similarity."""
        return (
            self.predicted_label is not None
            and 0.0 <= self.similarity <= 1.0
        )


# ---------------------------------------------------------------------------
# BaseRecognizer ABC
# ---------------------------------------------------------------------------

class BaseRecognizer(ABC):
    """
    Abstract base class for all face recognizer wrappers.

    Subclasses must implement:
      - build_gallery(pairs)
      - predict(face_crop, threshold, open_set)
      - name (property)

    Optional override:
      - produces_embeddings (property) — return False for LBPH

    Contract:
      - build_gallery() must be called before predict().
      - predict() returns RecognitionResult with similarity in [0.0, 1.0].
      - In open-set mode (open_set=True), if best similarity < threshold,
        predicted_label is "unknown" and is_unknown is True.
      - In closed-set mode (open_set=False), always returns the nearest
        gallery identity regardless of threshold.
      - If gallery is empty, returns RecognitionResult(None, 0.0).
      - Raises ImportError in __init__ if required library is missing.
    """

    @abstractmethod
    def build_gallery(
        self,
        pairs: List[Tuple[str, np.ndarray]],
    ) -> None:
        """
        Enroll a set of (identity_label, face_crop) pairs into the gallery.

        Multiple crops per identity are averaged into a single centroid
        (for embedding-based recognizers) or used to train the model (LBPH).

        Args:
            pairs: List of (identity_label, face_crop_bgr) tuples.
                   face_crop_bgr is a BGR numpy array, dtype uint8.

        Raises:
            ValueError: If pairs is empty.
        """
        ...

    @abstractmethod
    def predict(
        self,
        face_crop: np.ndarray,
        threshold: float = 0.5,
        open_set: bool = False,
    ) -> RecognitionResult:
        """
        Predict the identity of a single face crop.

        Args:
            face_crop:  BGR numpy array of the face to identify.
            threshold:  Similarity threshold for open-set rejection.
                        In open-set mode, probes with similarity < threshold
                        are returned as "unknown".
            open_set:   If True, enable open-set rejection.

        Returns:
            RecognitionResult with predicted_label and similarity score.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier used in filenames and logs."""
        ...

    @property
    def produces_embeddings(self) -> bool:
        """
        True if this recognizer produces fixed-length embedding vectors.
        False for LBPH (histogram-based, no fixed embedding).
        Used to gate embedding space analysis.
        """
        return True

    def clear_gallery(self) -> None:
        """Reset the gallery. Subclasses may override for cleanup."""
        pass

    # ------------------------------------------------------------------
    # Shared utility — L2-normalise a vector
    # ------------------------------------------------------------------

    @staticmethod
    def _l2_normalize(v: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(v)
        return v / norm if norm > 1e-10 else v

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between two vectors, result in [-1, 1]."""
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)
        if a_norm < 1e-10 or b_norm < 1e-10:
            return 0.0
        return float(np.dot(a, b) / (a_norm * b_norm))

    @staticmethod
    def _euclidean_to_similarity(distance: float, scale: float = 2.0) -> float:
        """
        Convert a non-negative Euclidean distance to a [0, 1] similarity score.
        Uses: similarity = exp(-distance / scale)
        scale=2.0 is calibrated for L2-normalised 512-dim ArcFace embeddings.
        """
        import math
        return float(math.exp(-distance / scale))
