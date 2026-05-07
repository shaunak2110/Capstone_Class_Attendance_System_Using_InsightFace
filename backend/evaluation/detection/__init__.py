"""
Detection layer — BaseDetector ABC and DetectionResult dataclass.

All concrete detector wrappers inherit from BaseDetector and must return
a list of DetectionResult objects with a uniform structure, regardless of
the underlying model.

Usage:
    from detection import BaseDetector, DetectionResult
    from detection.insightface_detector import InsightFaceDetector
    from detection.haarcascade_detector import HaarcascadeDetector
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

import numpy as np


@dataclass
class DetectionResult:
    """
    Standardised output for a single detected face.

    Attributes:
        bbox:       Bounding box as [x1, y1, x2, y2] in pixel coordinates
                    (top-left and bottom-right corners, clamped to image bounds).
        confidence: Detection confidence score in [0.0, 1.0].
        crop:       BGR numpy array of the cropped face region.
                    Shape: (H, W, 3), dtype uint8.
    """
    bbox: List[int]          # [x1, y1, x2, y2]
    confidence: float        # in [0.0, 1.0]
    crop: np.ndarray = field(repr=False)   # BGR face crop

    def __post_init__(self) -> None:
        # Coerce bbox elements to plain Python ints (ONNX may return numpy ints)
        self.bbox = [int(v) for v in self.bbox]
        self.confidence = float(self.confidence)

    @property
    def x1(self) -> int:
        return self.bbox[0]

    @property
    def y1(self) -> int:
        return self.bbox[1]

    @property
    def x2(self) -> int:
        return self.bbox[2]

    @property
    def y2(self) -> int:
        return self.bbox[3]

    @property
    def width(self) -> int:
        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        return max(0, self.y2 - self.y1)

    @property
    def area(self) -> int:
        return self.width * self.height

    def is_valid(self) -> bool:
        """Return True if the bounding box has positive area and valid confidence."""
        return (
            self.x1 < self.x2
            and self.y1 < self.y2
            and 0.0 <= self.confidence <= 1.0
            and self.crop is not None
            and self.crop.size > 0
        )


class BaseDetector(ABC):
    """
    Abstract base class for all face detector wrappers.

    Subclasses must implement:
      - detect(image_bgr) → List[DetectionResult]
      - name (property) → str

    Contract:
      - detect() accepts a BGR numpy array (uint8, any size).
      - detect() returns [] when no face is found (never raises on empty result).
      - detect() raises ImportError / FileNotFoundError in __init__ if the
        required library or model file is missing.
      - All returned DetectionResult objects satisfy result.is_valid() == True.
      - Bounding boxes are clamped to image bounds.
      - Confidence scores are in [0.0, 1.0].
    """

    @abstractmethod
    def detect(self, image_bgr: np.ndarray) -> List[DetectionResult]:
        """
        Detect all faces in a BGR image.

        Args:
            image_bgr: BGR numpy array, dtype uint8, shape (H, W, 3).

        Returns:
            List of DetectionResult objects, one per detected face.
            Returns an empty list if no face is detected.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Short identifier used in filenames and logs.
        Examples: "insightface", "haarcascade", "retinaface", "yolo".
        """
        ...

    # ------------------------------------------------------------------
    # Shared utility — crop a face from an image given a bounding box
    # ------------------------------------------------------------------

    @staticmethod
    def _crop_face(image_bgr: np.ndarray, bbox: List[int]) -> np.ndarray:
        """
        Extract and return the face crop from image_bgr using bbox.

        Clamps coordinates to image bounds before slicing.

        Args:
            image_bgr: Source BGR image.
            bbox:      [x1, y1, x2, y2] bounding box.

        Returns:
            BGR numpy array of the face crop (may be empty if bbox is degenerate).
        """
        h, w = image_bgr.shape[:2]
        x1 = max(0, int(bbox[0]))
        y1 = max(0, int(bbox[1]))
        x2 = min(w, int(bbox[2]))
        y2 = min(h, int(bbox[3]))
        return image_bgr[y1:y2, x1:x2].copy()
