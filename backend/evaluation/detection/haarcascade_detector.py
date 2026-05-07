"""
HaarcascadeDetector — face detection using OpenCV Haar Cascade classifier.

Uses haarcascade_frontalface_default.xml which ships with opencv-python.
No additional model files required.

Confidence scores are derived from the cascade's detection weight (not a
true probability). They are normalised to [0.0, 1.0] using a soft sigmoid
so that the output format matches other detectors.

Usage:
    from detection.haarcascade_detector import HaarcascadeDetector
    detector = HaarcascadeDetector()
    results = detector.detect(bgr_image)
    for r in results:
        print(r.bbox, r.confidence, r.crop.shape)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from detection import BaseDetector, DetectionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_cascade_file(cascade_name: str) -> Optional[Path]:
    """
    Locate a Haar cascade XML file bundled with OpenCV.

    Searches:
      1. cv2.data.haarcascades (standard install location)
      2. Common fallback paths
    """
    # Primary: cv2.data.haarcascades attribute (available in opencv-python >= 3.x)
    data_dir = getattr(cv2, "data", None)
    if data_dir is not None:
        haarcascades_dir = getattr(data_dir, "haarcascades", None)
        if haarcascades_dir:
            candidate = Path(haarcascades_dir) / cascade_name
            if candidate.exists():
                return candidate

    # Fallback: search common OpenCV install paths
    import sys
    for site_pkg in sys.path:
        candidate = Path(site_pkg) / "cv2" / "data" / cascade_name
        if candidate.exists():
            return candidate

    return None


def _weight_to_confidence(weight: float, scale: float = 0.1) -> float:
    """
    Convert a Haar cascade detection weight to a [0, 1] confidence score.

    The cascade returns integer neighbour counts (higher = more confident).
    We apply a soft sigmoid: conf = 1 / (1 + exp(-scale * weight)).
    Clipped to [0.0, 1.0].
    """
    import math
    try:
        conf = 1.0 / (1.0 + math.exp(-scale * float(weight)))
    except OverflowError:
        conf = 0.0 if weight < 0 else 1.0
    return max(0.0, min(1.0, conf))


# ---------------------------------------------------------------------------
# HaarcascadeDetector
# ---------------------------------------------------------------------------

class HaarcascadeDetector(BaseDetector):
    """
    Face detector using OpenCV Haar Cascade (haarcascade_frontalface_default.xml).

    Suitable for frontal faces under reasonable lighting. Faster than deep
    learning detectors but less accurate on profile or occluded faces.

    Args:
        cascade_path:    Path to the cascade XML file. If None, auto-detected
                         from the OpenCV data directory.
        scale_factor:    Image pyramid scale factor. Default 1.1.
        min_neighbors:   Minimum neighbours for a valid detection. Default 5.
        min_size:        Minimum face size in pixels (width, height). Default (30, 30).

    Raises:
        FileNotFoundError: If the cascade XML file cannot be found.
    """

    _CASCADE_NAME = "haarcascade_frontalface_default.xml"

    def __init__(
        self,
        cascade_path: Optional[str | Path] = None,
        scale_factor: float = 1.1,
        min_neighbors: int = 5,
        min_size: tuple = (30, 30),
    ) -> None:
        if cascade_path is not None:
            xml_path = Path(cascade_path)
        else:
            xml_path = _find_cascade_file(self._CASCADE_NAME)

        if xml_path is None or not xml_path.exists():
            raise FileNotFoundError(
                f"Haar cascade file not found: {self._CASCADE_NAME}\n"
                f"Expected in OpenCV data directory (cv2.data.haarcascades).\n"
                f"Ensure opencv-python is installed: pip install opencv-python\n"
                f"Or pass cascade_path= explicitly."
            )

        self._cascade = cv2.CascadeClassifier(str(xml_path))
        if self._cascade.empty():
            raise FileNotFoundError(
                f"Failed to load cascade classifier from: {xml_path}\n"
                f"The file may be corrupt or incompatible."
            )

        self._scale_factor = scale_factor
        self._min_neighbors = min_neighbors
        self._min_size = min_size
        self._cascade_path = xml_path

    # ------------------------------------------------------------------
    # BaseDetector interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "haarcascade"

    def detect(self, image_bgr: np.ndarray) -> List[DetectionResult]:
        """
        Detect frontal faces in a BGR image using Haar Cascade.

        Args:
            image_bgr: BGR numpy array, dtype uint8, shape (H, W, 3).

        Returns:
            List of DetectionResult objects sorted by confidence (descending).
            Returns [] if no face is detected.
        """
        if image_bgr is None or image_bgr.size == 0:
            return []

        # Convert to grayscale for cascade detection
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)  # improve contrast for varied lighting

        # detectMultiScale3 returns (rects, weights) — weights are neighbour counts
        detections, _, weights = self._cascade.detectMultiScale3(
            gray,
            scaleFactor=self._scale_factor,
            minNeighbors=self._min_neighbors,
            minSize=self._min_size,
            outputRejectLevels=True,
        )

        if len(detections) == 0:
            return []

        h, w = image_bgr.shape[:2]
        results: List[DetectionResult] = []

        for i, (x, y, fw, fh) in enumerate(detections):
            x1 = max(0, int(x))
            y1 = max(0, int(y))
            x2 = min(w, int(x + fw))
            y2 = min(h, int(y + fh))

            # Skip degenerate boxes
            if x2 <= x1 or y2 <= y1:
                continue

            bbox = [x1, y1, x2, y2]
            weight = float(weights[i]) if i < len(weights) else 1.0
            confidence = _weight_to_confidence(weight)

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
