"""
LBPHRecognizer — face recognition using OpenCV Local Binary Pattern Histograms.

LBPH is a classical, non-deep-learning recognizer. It trains on grayscale face
crops and returns a confidence distance (lower = more similar). This wrapper
converts the distance to a [0, 1] similarity score for a uniform interface.

No external model files required — uses cv2.face.LBPHFaceRecognizer_create().

Note: LBPH does not produce fixed-length embedding vectors.
      produces_embeddings returns False, so embedding space analysis is skipped.

Usage:
    from recognition.lbph_recognizer import LBPHRecognizer

    rec = LBPHRecognizer()
    rec.build_gallery([("alice", crop1), ("alice", crop2), ("bob", crop3)])
    result = rec.predict(probe_crop, threshold=0.5)
    print(result.predicted_label, result.similarity)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from recognition import BaseRecognizer, RecognitionResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Availability flag — checked by ExperimentRunner before instantiating
# ---------------------------------------------------------------------------
LBPH_AVAILABLE: bool = hasattr(cv2, "face")

# LBPH confidence distances: 0 = perfect match, higher = worse.
# Empirically, distances > 100 are typically wrong matches.
# We use this scale to normalise to [0, 1].
_LBPH_DISTANCE_SCALE = 100.0


def _distance_to_similarity(distance: float, scale: float = _LBPH_DISTANCE_SCALE) -> float:
    """
    Convert LBPH confidence distance to a [0, 1] similarity score.

    Uses: similarity = exp(-distance / scale)
    At distance=0   → similarity=1.0 (perfect match)
    At distance=100 → similarity≈0.37
    At distance=200 → similarity≈0.14
    """
    import math
    return float(math.exp(-max(0.0, distance) / scale))


class LBPHRecognizer(BaseRecognizer):
    """
    Face recognizer using OpenCV LBPH (Local Binary Pattern Histograms).

    Trains one LBPHFaceRecognizer on all gallery crops. Identity labels are
    mapped to integer class IDs internally.

    Args:
        radius:        LBPH radius parameter. Default 1.
        neighbors:     LBPH neighbors parameter. Default 8.
        grid_x:        LBPH grid_x parameter. Default 8.
        grid_y:        LBPH grid_y parameter. Default 8.
        face_size:     Resize all crops to this (width, height) before training
                       and prediction. Default (100, 100).
        distance_scale: Scale factor for distance→similarity conversion.
                        Default 100.0.

    Raises:
        AttributeError: If cv2.face module is not available (opencv-contrib required).
    """

    def __init__(
        self,
        radius: int = 1,
        neighbors: int = 8,
        grid_x: int = 8,
        grid_y: int = 8,
        face_size: Tuple[int, int] = (100, 100),
        distance_scale: float = _LBPH_DISTANCE_SCALE,
    ) -> None:
        if not hasattr(cv2, "face"):
            raise ImportError(
                "cv2.face module not found. "
                "Install opencv-contrib-python: pip install opencv-contrib-python\n"
                "On Windows, if access is denied during install, close all Python "
                "processes and retry, or use: pip install opencv-contrib-python --user"
            )

        self._face_size = face_size
        self._distance_scale = distance_scale

        self._model = cv2.face.LBPHFaceRecognizer_create(
            radius=radius,
            neighbors=neighbors,
            grid_x=grid_x,
            grid_y=grid_y,
        )

        # Bidirectional label ↔ integer ID mapping
        self._label_to_id: Dict[str, int] = {}
        self._id_to_label: Dict[int, str] = {}
        self._is_trained: bool = False

    # ------------------------------------------------------------------
    # BaseRecognizer interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "lbph"

    @property
    def produces_embeddings(self) -> bool:
        """LBPH does not produce fixed-length embedding vectors."""
        return False

    def build_gallery(
        self,
        pairs: List[Tuple[str, np.ndarray]],
    ) -> None:
        """
        Train the LBPH model on all (identity_label, face_crop) pairs.

        Multiple crops per identity are all used for training (LBPH benefits
        from multiple examples per class).

        Args:
            pairs: List of (identity_label, face_crop_bgr) tuples.

        Raises:
            ValueError: If pairs is empty or no valid crops are found.
        """
        if not pairs:
            raise ValueError("build_gallery() requires at least one (label, crop) pair.")

        # Reset state
        self._label_to_id.clear()
        self._id_to_label.clear()
        self._is_trained = False

        # Assign integer IDs to identity labels
        unique_labels = sorted({label for label, _ in pairs})
        for idx, label in enumerate(unique_labels):
            self._label_to_id[label] = idx
            self._id_to_label[idx] = label

        # Prepare training data
        train_images: List[np.ndarray] = []
        train_labels: List[int] = []
        skipped = 0

        for label, crop in pairs:
            gray = self._preprocess(crop)
            if gray is None:
                skipped += 1
                continue
            train_images.append(gray)
            train_labels.append(self._label_to_id[label])

        if not train_images:
            raise ValueError(
                "No valid face crops found in gallery pairs. "
                "Ensure crops are non-empty BGR images."
            )

        if skipped > 0:
            logger.warning(
                "LBPHRecognizer: %d crop(s) skipped (invalid image).", skipped
            )

        self._model.train(train_images, np.array(train_labels, dtype=np.int32))
        self._is_trained = True

        logger.info(
            "LBPHRecognizer: trained on %d crops across %d identities "
            "(%d skipped).",
            len(train_images), len(unique_labels), skipped,
        )

    def predict(
        self,
        face_crop: np.ndarray,
        threshold: float = 0.5,
        open_set: bool = False,
    ) -> RecognitionResult:
        """
        Predict the identity of a face crop using LBPH.

        Args:
            face_crop:  BGR numpy array of the face to identify.
            threshold:  Similarity threshold for open-set rejection.
                        In open-set mode, probes with similarity < threshold
                        are returned as "unknown".
            open_set:   If True, enable open-set rejection.

        Returns:
            RecognitionResult with predicted_label and similarity in [0, 1].
        """
        if not self._is_trained or not self._id_to_label:
            return RecognitionResult(predicted_label=None, similarity=0.0)

        gray = self._preprocess(face_crop)
        if gray is None:
            return RecognitionResult(
                predicted_label="unknown" if open_set else None,
                similarity=0.0,
                is_unknown=True,
            )

        predicted_id, confidence = self._model.predict(gray)
        # confidence is a distance: 0 = perfect, higher = worse
        similarity = _distance_to_similarity(confidence, self._distance_scale)

        predicted_label = self._id_to_label.get(int(predicted_id))
        if predicted_label is None:
            # Unexpected ID — treat as unknown
            return RecognitionResult(
                predicted_label="unknown",
                similarity=similarity,
                is_unknown=True,
            )

        # Open-set rejection
        if open_set and similarity < threshold:
            return RecognitionResult(
                predicted_label="unknown",
                similarity=similarity,
                is_unknown=True,
            )

        return RecognitionResult(
            predicted_label=predicted_label,
            similarity=similarity,
            is_unknown=False,
        )

    def clear_gallery(self) -> None:
        self._label_to_id.clear()
        self._id_to_label.clear()
        self._is_trained = False
        # Re-create a fresh model
        self._model = cv2.face.LBPHFaceRecognizer_create()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _preprocess(self, crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Convert a BGR crop to a grayscale image resized to face_size.

        Returns None if the crop is invalid.
        """
        if crop is None or crop.size == 0:
            return None
        try:
            if crop.ndim == 3:
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            else:
                gray = crop.copy()
            resized = cv2.resize(gray, self._face_size, interpolation=cv2.INTER_LINEAR)
            return resized
        except Exception as exc:
            logger.debug("LBPHRecognizer._preprocess error: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Pure-numpy fallback — used when cv2.face is not available
# ---------------------------------------------------------------------------

def _compute_lbp_histogram(gray: np.ndarray, grid: int = 8) -> np.ndarray:
    """
    Compute a simplified LBP histogram over a grid of cells.

    This is a lightweight numpy implementation used as a fallback when
    cv2.face is not available. It produces a 1D feature vector suitable
    for chi-squared distance matching.
    """
    h, w = gray.shape
    cell_h = h // grid
    cell_w = w // grid
    hist_bins = 256
    feature = []

    for row in range(grid):
        for col in range(grid):
            cell = gray[
                row * cell_h:(row + 1) * cell_h,
                col * cell_w:(col + 1) * cell_w,
            ]
            if cell.size == 0:
                feature.extend([0] * hist_bins)
                continue
            # Simple LBP: compare each pixel to its 8 neighbours
            lbp = np.zeros_like(cell, dtype=np.uint8)
            for dy, dx in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
                shifted = np.roll(np.roll(cell, dy, axis=0), dx, axis=1)
                lbp = (lbp << 1) | (cell >= shifted).astype(np.uint8)
            hist, _ = np.histogram(lbp.ravel(), bins=hist_bins, range=(0, 256))
            feature.extend(hist.tolist())

    return np.array(feature, dtype=np.float32)


class LBPHFallbackRecognizer(BaseRecognizer):
    """
    Pure-numpy LBPH-style recognizer — used when cv2.face is not available.

    Computes LBP histograms over a grid of cells and matches using
    chi-squared distance. Produces the same interface as LBPHRecognizer.

    This is intended for testing and environments where opencv-contrib-python
    cannot be installed. For production use, prefer LBPHRecognizer.
    """

    def __init__(
        self,
        face_size: Tuple[int, int] = (100, 100),
        grid: int = 8,
        distance_scale: float = _LBPH_DISTANCE_SCALE,
    ) -> None:
        self._face_size = face_size
        self._grid = grid
        self._distance_scale = distance_scale
        self._gallery_features: Dict[str, np.ndarray] = {}  # {label: mean_histogram}
        self._label_to_id: Dict[str, int] = {}
        self._id_to_label: Dict[int, str] = {}
        self._is_trained: bool = False

    @property
    def name(self) -> str:
        return "lbph"

    @property
    def produces_embeddings(self) -> bool:
        return False

    def build_gallery(self, pairs: List[Tuple[str, np.ndarray]]) -> None:
        if not pairs:
            raise ValueError("build_gallery() requires at least one (label, crop) pair.")

        self._gallery_features.clear()
        self._label_to_id.clear()
        self._id_to_label.clear()
        self._is_trained = False

        grouped: Dict[str, List[np.ndarray]] = {}
        skipped = 0

        for label, crop in pairs:
            gray = self._preprocess(crop)
            if gray is None:
                skipped += 1
                continue
            feat = _compute_lbp_histogram(gray, self._grid)
            grouped.setdefault(label, []).append(feat)

        if not grouped:
            raise ValueError("No valid face crops found in gallery pairs.")

        unique_labels = sorted(grouped.keys())
        for idx, label in enumerate(unique_labels):
            self._label_to_id[label] = idx
            self._id_to_label[idx] = label
            feats = np.stack(grouped[label], axis=0)
            self._gallery_features[label] = np.mean(feats, axis=0)

        self._is_trained = True
        if skipped:
            logger.warning("LBPHFallbackRecognizer: %d crop(s) skipped.", skipped)

    def predict(
        self,
        face_crop: np.ndarray,
        threshold: float = 0.5,
        open_set: bool = False,
    ) -> RecognitionResult:
        if not self._is_trained or not self._gallery_features:
            return RecognitionResult(predicted_label=None, similarity=0.0)

        gray = self._preprocess(face_crop)
        if gray is None:
            return RecognitionResult(
                predicted_label="unknown" if open_set else None,
                similarity=0.0,
                is_unknown=True,
            )

        probe_feat = _compute_lbp_histogram(gray, self._grid)

        best_label: Optional[str] = None
        best_dist = float("inf")

        for label, gallery_feat in self._gallery_features.items():
            # Chi-squared distance
            denom = probe_feat + gallery_feat + 1e-10
            dist = float(np.sum((probe_feat - gallery_feat) ** 2 / denom))
            if dist < best_dist:
                best_dist = dist
                best_label = label

        similarity = _distance_to_similarity(best_dist, self._distance_scale)

        # Open-set rejection: threshold=1.0 means "always reject"
        if open_set and similarity < threshold:
            return RecognitionResult(
                predicted_label="unknown",
                similarity=similarity,
                is_unknown=True,
            )

        return RecognitionResult(
            predicted_label=best_label,
            similarity=similarity,
            is_unknown=False,
        )

    def clear_gallery(self) -> None:
        self._gallery_features.clear()
        self._label_to_id.clear()
        self._id_to_label.clear()
        self._is_trained = False

    def _preprocess(self, crop: np.ndarray) -> Optional[np.ndarray]:
        if crop is None or crop.size == 0:
            return None
        try:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop.copy()
            return cv2.resize(gray, self._face_size, interpolation=cv2.INTER_LINEAR)
        except Exception:
            return None
