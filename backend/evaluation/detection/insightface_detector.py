"""
InsightFaceDetector — face detection using InsightFace buffalo_l (det_10g.onnx).

This is a standalone wrapper for the evaluation pipeline.
It does NOT import from the production backend (backend/model/).
It uses the same buffalo_l model pack already present in the workspace.

Model path resolution (in priority order):
  1. Explicit path passed to __init__(model_dir=...)
  2. Environment variable BUFFALO_L_DIR
  3. Auto-search: walks up from this file's location looking for buffalo_l/

Usage:
    from detection.insightface_detector import InsightFaceDetector
    detector = InsightFaceDetector()
    results = detector.detect(bgr_image)
    for r in results:
        print(r.bbox, r.confidence, r.crop.shape)
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from detection import BaseDetector, DetectionResult


# ---------------------------------------------------------------------------
# ONNX provider helpers (identical logic to production engine, but standalone)
# ---------------------------------------------------------------------------

def _onnx_cuda_available() -> bool:
    """Return True only when the CUDA ONNX provider DLL is actually loadable."""
    try:
        import onnxruntime as ort
    except Exception:
        return False
    if "CUDAExecutionProvider" not in set(ort.get_available_providers()):
        return False
    provider_lib = os.path.join(
        os.path.dirname(ort.__file__), "capi", "onnxruntime_providers_cuda.dll"
    )
    if not os.path.exists(provider_lib):
        return False
    try:
        ctypes.WinDLL(provider_lib)
        return True
    except OSError:
        return False


def _find_buffalo_l_dir() -> Optional[Path]:
    """
    Walk up the directory tree from this file looking for a buffalo_l/ folder
    that contains det_10g.onnx.
    """
    current = Path(__file__).resolve().parent
    for _ in range(6):  # search up to 6 levels
        candidate = current / "buffalo_l"
        if (candidate / "det_10g.onnx").exists():
            return candidate
        current = current.parent
    return None


# ---------------------------------------------------------------------------
# InsightFaceDetector
# ---------------------------------------------------------------------------

class InsightFaceDetector(BaseDetector):
    """
    Face detector using InsightFace buffalo_l (det_10g.onnx).

    Wraps insightface.app.FaceAnalysis in detection-only mode.
    Returns DetectionResult objects with bbox, confidence, and face crop.

    Args:
        model_dir:  Path to the directory containing buffalo_l model files.
                    If None, auto-detected from BUFFALO_L_DIR env var or
                    by walking up the directory tree.
        det_size:   Detection input size (width, height). Default (640, 640).

    Raises:
        ImportError:      If the insightface package is not installed.
        FileNotFoundError: If det_10g.onnx cannot be found.
    """

    def __init__(
        self,
        model_dir: Optional[str | Path] = None,
        det_size: tuple = (640, 640),
    ) -> None:
        try:
            import insightface  # noqa: F401 — check import before heavy init
            from insightface.app import FaceAnalysis
        except ImportError as exc:
            raise ImportError(
                "insightface is not installed. "
                "Run: pip install insightface onnxruntime"
            ) from exc

        # Resolve model directory
        if model_dir is not None:
            resolved = Path(model_dir)
        elif "BUFFALO_L_DIR" in os.environ:
            resolved = Path(os.environ["BUFFALO_L_DIR"])
        else:
            resolved = _find_buffalo_l_dir()

        if resolved is None or not (resolved / "det_10g.onnx").exists():
            searched = resolved or "<not found>"
            raise FileNotFoundError(
                f"buffalo_l/det_10g.onnx not found.\n"
                f"Searched: {searched}\n"
                f"Set BUFFALO_L_DIR env var or pass model_dir= explicitly.\n"
                f"Expected layout: <model_dir>/det_10g.onnx"
            )

        self._model_dir = resolved
        self._det_size = det_size

        # InsightFace expects the *parent* of the model pack folder as root_dir,
        # and the pack name as the folder name.
        root_dir = str(resolved.parent)
        pack_name = resolved.name  # "buffalo_l"

        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if _onnx_cuda_available()
            else ["CPUExecutionProvider"]
        )

        self._app = FaceAnalysis(
            name=pack_name,
            root=root_dir,
            providers=providers,
            allowed_modules=["detection"],   # detection only — skip recognition
        )
        ctx_id = 0 if "CUDAExecutionProvider" in providers else -1
        self._app.prepare(ctx_id=ctx_id, det_size=det_size)

    # ------------------------------------------------------------------
    # BaseDetector interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "insightface"

    def detect(self, image_bgr: np.ndarray) -> List[DetectionResult]:
        """
        Detect all faces in a BGR image using InsightFace buffalo_l.

        Args:
            image_bgr: BGR numpy array, dtype uint8, shape (H, W, 3).

        Returns:
            List of DetectionResult objects sorted by confidence (descending).
            Returns [] if no face is detected.
        """
        if image_bgr is None or image_bgr.size == 0:
            return []

        faces = self._app.get(image_bgr)
        if not faces:
            return []

        h, w = image_bgr.shape[:2]
        results: List[DetectionResult] = []

        for face in faces:
            # bbox from InsightFace is float32 [x1, y1, x2, y2]
            x1, y1, x2, y2 = face.bbox.astype(float).tolist()

            # Clamp to image bounds
            x1 = max(0.0, x1)
            y1 = max(0.0, y1)
            x2 = min(float(w), x2)
            y2 = min(float(h), y2)

            bbox = [int(x1), int(y1), int(x2), int(y2)]

            # Skip degenerate boxes
            if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                continue

            confidence = float(getattr(face, "det_score", 1.0))
            confidence = max(0.0, min(1.0, confidence))

            crop = self._crop_face(image_bgr, bbox)
            if crop.size == 0:
                continue

            results.append(DetectionResult(
                bbox=bbox,
                confidence=confidence,
                crop=crop,
            ))

        # Sort by confidence descending
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results
