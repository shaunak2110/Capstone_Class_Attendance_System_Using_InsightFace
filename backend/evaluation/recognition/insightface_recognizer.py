"""
InsightFaceRecognizer — face recognition using InsightFace buffalo_l ArcFace.

Generates 512-dim L2-normalised embeddings via w600k_r50.onnx.
Matching uses cosine similarity (dot product on L2-normalised vectors).

KEY DESIGN: Direct ONNX embedding extraction
---------------------------------------------
This recognizer calls the ArcFace ONNX model (w600k_r50.onnx) DIRECTLY via
onnxruntime, bypassing FaceAnalysis.get() entirely.

Why: FaceAnalysis.get() runs a full detection pass on the input image before
extracting embeddings. When the input is already a face crop from the
DetectionPipeline, the second detection pass frequently fails (tight crops
have no context for the detector), producing zero embeddings and 0.0 similarity.

Direct ONNX path:
  face_crop (BGR, any size)
    → resize to 112×112
    → BGR→RGB
    → normalize: (pixel - 127.5) / 127.5  → float32 in [-1, 1]
    → transpose: (H, W, C) → (1, C, H, W)
    → ONNX inference → (1, 512) embedding
    → L2-normalize → (512,) unit vector

Model path resolution (in priority order):
  1. Explicit model_dir= argument
  2. BUFFALO_L_DIR environment variable
  3. Auto-search: walks up from this file looking for buffalo_l/

Usage:
    from recognition.insightface_recognizer import InsightFaceRecognizer

    rec = InsightFaceRecognizer()
    rec.build_gallery([("alice", crop1), ("alice", crop2), ("bob", crop3)])
    result = rec.predict(probe_crop, threshold=0.45)
    print(result.predicted_label, result.similarity)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from recognition import BaseRecognizer, RecognitionResult

logger = logging.getLogger(__name__)

# ArcFace model constants
_INPUT_SIZE = (112, 112)          # (width, height)
_INPUT_MEAN = 127.5
_INPUT_STD  = 127.5
_EMBED_DIM  = 512


# ---------------------------------------------------------------------------
# Model path helpers
# ---------------------------------------------------------------------------

def _find_buffalo_l_dir() -> Optional[Path]:
    """Walk up the directory tree looking for buffalo_l/w600k_r50.onnx."""
    current = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = current / "buffalo_l"
        if (candidate / "w600k_r50.onnx").exists():
            return candidate
        current = current.parent
    return None


# ---------------------------------------------------------------------------
# Direct ONNX embedding extractor
# ---------------------------------------------------------------------------

class _ArcFaceONNX:
    """
    Thin wrapper around the ArcFace ONNX model for direct embedding extraction.

    Accepts a BGR face crop of any size, resizes to 112×112, normalises,
    and returns a 512-dim L2-normalised float32 embedding.

    No face detection is performed — the input is assumed to already be a
    face crop.
    """

    def __init__(self, model_path: Path) -> None:
        import onnxruntime as ort

        providers = ["CPUExecutionProvider"]
        # Try CUDA if available
        try:
            import ctypes
            provider_lib = os.path.join(
                os.path.dirname(ort.__file__), "capi",
                "onnxruntime_providers_cuda.dll",
            )
            if (
                "CUDAExecutionProvider" in ort.get_available_providers()
                and os.path.exists(provider_lib)
            ):
                ctypes.WinDLL(provider_lib)
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        except Exception:
            pass

        self._session = ort.InferenceSession(str(model_path), providers=providers)
        self._input_name = self._session.get_inputs()[0].name
        self._output_name = self._session.get_outputs()[0].name
        logger.debug(
            "ArcFaceONNX loaded: %s  input=%s  output=%s",
            model_path.name, self._input_name, self._output_name,
        )

    def embed(self, face_crop_bgr: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract a 512-dim L2-normalised embedding from a BGR face crop.

        Args:
            face_crop_bgr: BGR numpy array, any size, dtype uint8 or float.

        Returns:
            float32 numpy array of shape (512,), L2-normalised.
            Returns None if the crop is empty or inference fails.
        """
        if face_crop_bgr is None or face_crop_bgr.size == 0:
            return None

        try:
            # 1. Resize to 112×112
            resized = cv2.resize(
                face_crop_bgr, _INPUT_SIZE, interpolation=cv2.INTER_LINEAR
            )

            # 2. BGR → RGB
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

            # 3. Normalise: (pixel - 127.5) / 127.5  →  float32 in [-1, 1]
            blob = (rgb.astype(np.float32) - _INPUT_MEAN) / _INPUT_STD

            # 4. HWC → NCHW  (1, 3, 112, 112)
            blob = np.transpose(blob, (2, 0, 1))[np.newaxis, ...]

            # 5. ONNX inference
            outputs = self._session.run(
                [self._output_name], {self._input_name: blob}
            )
            emb = outputs[0][0].astype(np.float32)  # (512,)

            # 6. L2-normalise
            norm = np.linalg.norm(emb)
            if norm < 1e-10:
                return None
            return emb / norm

        except Exception as exc:
            logger.debug("ArcFaceONNX.embed error: %s", exc)
            return None


# ---------------------------------------------------------------------------
# InsightFaceRecognizer
# ---------------------------------------------------------------------------

class InsightFaceRecognizer(BaseRecognizer):
    """
    Face recognizer using InsightFace buffalo_l ArcFace (w600k_r50.onnx).

    Embeddings are extracted by calling the ArcFace ONNX model DIRECTLY —
    no FaceAnalysis.get() / face detection is performed on the input crops.
    This is critical when the inputs are already face crops from a detector.

    Gallery embeddings are averaged per identity into a single L2-normalised
    centroid. Matching uses cosine similarity (dot product on unit vectors).

    Args:
        model_dir:  Path to the buffalo_l directory. Auto-detected if None.

    Raises:
        ImportError:       If onnxruntime is not installed.
        FileNotFoundError: If w600k_r50.onnx cannot be found.
    """

    EMBEDDING_DIM = _EMBED_DIM

    def __init__(self, model_dir: Optional[str | Path] = None) -> None:
        try:
            import onnxruntime  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "onnxruntime is not installed. "
                "Run: pip install onnxruntime"
            ) from exc

        # Resolve model directory
        if model_dir is not None:
            resolved = Path(model_dir)
        elif "BUFFALO_L_DIR" in os.environ:
            resolved = Path(os.environ["BUFFALO_L_DIR"])
        else:
            resolved = _find_buffalo_l_dir()

        model_path = resolved / "w600k_r50.onnx" if resolved else None
        if model_path is None or not model_path.exists():
            raise FileNotFoundError(
                f"buffalo_l/w600k_r50.onnx not found.\n"
                f"Searched: {resolved or '<not found>'}\n"
                f"Set BUFFALO_L_DIR env var or pass model_dir= explicitly."
            )

        self._model_dir = resolved
        self._arcface = _ArcFaceONNX(model_path)

        # Gallery: {identity_label: centroid_embedding (512,)}
        self._gallery: Dict[str, np.ndarray] = {}
        # Raw per-identity embeddings (before averaging)
        self._raw_embeddings: Dict[str, List[np.ndarray]] = {}

        # Diagnostics counters
        self._embed_attempts: int = 0
        self._embed_failures: int = 0

    # ------------------------------------------------------------------
    # BaseRecognizer interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "insightface"

    @property
    def produces_embeddings(self) -> bool:
        return True

    def build_gallery(
        self,
        pairs: List[Tuple[str, np.ndarray]],
    ) -> None:
        """
        Enroll (identity_label, face_crop) pairs into the gallery.

        Embeddings are extracted directly via the ArcFace ONNX model.
        Multiple crops per identity are averaged into a single L2-normalised
        centroid.

        Args:
            pairs: List of (identity_label, face_crop_bgr) tuples.

        Raises:
            ValueError: If pairs is empty or no embeddings can be extracted.
        """
        if not pairs:
            raise ValueError("build_gallery() requires at least one (label, crop) pair.")

        self._gallery.clear()
        self._raw_embeddings.clear()
        self._embed_attempts = 0
        self._embed_failures = 0

        grouped: Dict[str, List[np.ndarray]] = {}

        for label, crop in pairs:
            self._embed_attempts += 1
            emb = self._arcface.embed(crop)
            if emb is None:
                self._embed_failures += 1
                continue
            grouped.setdefault(label, []).append(emb)

        if self._embed_failures > 0:
            logger.warning(
                "InsightFaceRecognizer.build_gallery: %d/%d crops failed embedding "
                "(%.1f%% failure rate).",
                self._embed_failures, self._embed_attempts,
                100.0 * self._embed_failures / self._embed_attempts,
            )

        if not grouped:
            raise ValueError(
                "No embeddings could be extracted from any gallery crop. "
                "Ensure crops are valid BGR face images."
            )

        for label, embeddings in grouped.items():
            self._raw_embeddings[label] = embeddings
            centroid = np.mean(np.stack(embeddings, axis=0), axis=0)
            norm = np.linalg.norm(centroid)
            self._gallery[label] = centroid / norm if norm > 1e-10 else centroid

        logger.info(
            "InsightFaceRecognizer: gallery built — %d identities, "
            "%d/%d crops embedded successfully.",
            len(self._gallery),
            self._embed_attempts - self._embed_failures,
            self._embed_attempts,
        )

    def predict(
        self,
        face_crop: np.ndarray,
        threshold: float = 0.45,
        open_set: bool = False,
    ) -> RecognitionResult:
        """
        Predict the identity of a face crop using cosine similarity.

        Embedding is extracted directly via the ArcFace ONNX model —
        no face detection is performed on the input crop.

        Args:
            face_crop:  BGR numpy array of the face to identify.
            threshold:  Normalised cosine similarity threshold for open-set
                        rejection. Range [0, 1]. Default 0.45.
                        Note: normalised similarity = (raw_cosine + 1) / 2.
                        Genuine ArcFace pairs typically score 0.55–0.80.
            open_set:   If True, return "unknown" when best similarity < threshold.

        Returns:
            RecognitionResult with predicted_label and similarity in [0, 1].
        """
        if not self._gallery:
            return RecognitionResult(predicted_label=None, similarity=0.0)

        self._embed_attempts += 1
        probe_emb = self._arcface.embed(face_crop)

        if probe_emb is None:
            self._embed_failures += 1
            logger.debug("InsightFaceRecognizer.predict: embedding failed for probe crop.")
            return RecognitionResult(
                predicted_label="unknown" if open_set else None,
                similarity=0.0,
                is_unknown=open_set,
            )

        # Cosine similarity = dot product (both vectors are L2-normalised)
        best_label: Optional[str] = None
        best_raw_sim: float = -1.0

        for label, centroid in self._gallery.items():
            raw_sim = float(np.dot(probe_emb, centroid))
            if raw_sim > best_raw_sim:
                best_raw_sim = raw_sim
                best_label = label

        # Normalise from [-1, 1] to [0, 1]
        normalised_sim = (best_raw_sim + 1.0) / 2.0

        if open_set and normalised_sim < threshold:
            return RecognitionResult(
                predicted_label="unknown",
                similarity=normalised_sim,
                is_unknown=True,
            )

        return RecognitionResult(
            predicted_label=best_label,
            similarity=normalised_sim,
            is_unknown=False,
        )

    def clear_gallery(self) -> None:
        self._gallery.clear()
        self._raw_embeddings.clear()
        self._embed_attempts = 0
        self._embed_failures = 0

    def get_gallery_embeddings(self) -> Dict[str, np.ndarray]:
        """Return a copy of the gallery centroids {label: embedding}."""
        return dict(self._gallery)

    def get_raw_embeddings(self) -> Dict[str, List[np.ndarray]]:
        """Return all per-identity raw embeddings (before averaging)."""
        return dict(self._raw_embeddings)

    def embedding_stats(self) -> dict:
        """Return embedding attempt/failure counts for diagnostics."""
        return {
            "attempts": self._embed_attempts,
            "failures": self._embed_failures,
            "success_rate": (
                (self._embed_attempts - self._embed_failures) / self._embed_attempts
                if self._embed_attempts > 0 else 0.0
            ),
        }
