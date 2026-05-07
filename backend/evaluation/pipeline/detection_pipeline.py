"""
DetectionPipeline — runs a BaseDetector over a list of images and records
per-image detection results with timing.

Accepts image paths (str/Path) or pre-loaded BGR numpy arrays.
Preprocessing (resize, clip) is applied before detection.
Timing uses time.perf_counter() and excludes image loading/preprocessing.

Usage:
    from detection.haarcascade_detector import HaarcascadeDetector
    from pipeline.detection_pipeline import DetectionPipeline, DetectionRecord

    detector = HaarcascadeDetector()
    pipeline = DetectionPipeline(detector, image_size=(640, 640))

    records = pipeline.run(
        images=["path/to/img1.jpg", bgr_array],
        true_labels=["alice", "alice"],
    )
    for r in records:
        print(r.image_id, r.detected, r.detection_ms, len(r.detections))
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

from detection import BaseDetector, DetectionResult

logger = logging.getLogger(__name__)

# Type alias for flexible image input
ImageInput = Union[str, Path, np.ndarray]


# ---------------------------------------------------------------------------
# DetectionRecord — one record per input image
# ---------------------------------------------------------------------------

@dataclass
class DetectionRecord:
    """
    Detection result for a single input image.

    Attributes:
        image_id:           String identifier — file path for path inputs,
                            "array_<index>" for numpy inputs.
        true_label:         Ground-truth identity label (from the caller).
                            None if not provided.
        detections:         List of DetectionResult objects from the detector.
                            Empty list if no face was detected.
        detected:           True if at least one face was detected.
        detection_ms:       Wall-clock time for the detector.detect() call only
                            (excludes loading and preprocessing).
        ground_truth_boxes: Optional list of GT bounding boxes [[x1,y1,x2,y2],...]
                            loaded from annotations.json. None if not provided.
        image_shape:        (height, width) of the preprocessed image.
    """
    image_id: str
    true_label: Optional[str]
    detections: List[DetectionResult]
    detected: bool
    detection_ms: float
    ground_truth_boxes: Optional[List[List[int]]] = None
    image_shape: Optional[Tuple[int, int]] = None  # (H, W)

    @property
    def best_detection(self) -> Optional[DetectionResult]:
        """Return the highest-confidence detection, or None if empty."""
        if not self.detections:
            return None
        return max(self.detections, key=lambda d: d.confidence)

    @property
    def face_count(self) -> int:
        return len(self.detections)


# ---------------------------------------------------------------------------
# DetectionPipeline
# ---------------------------------------------------------------------------

class DetectionPipeline:
    """
    Runs a BaseDetector over a batch of images and returns DetectionRecords.

    Args:
        detector:    Any BaseDetector implementation.
        image_size:  (width, height) to resize images before detection.
                     Default (640, 640). Set to None to skip resizing.
    """

    def __init__(
        self,
        detector: BaseDetector,
        image_size: Optional[Tuple[int, int]] = (640, 640),
    ) -> None:
        self._detector = detector
        self._image_size = image_size

    @property
    def detector(self) -> BaseDetector:
        return self._detector

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        images: List[ImageInput],
        true_labels: Optional[List[Optional[str]]] = None,
        annotations: Optional[Dict[str, List[List[int]]]] = None,
    ) -> List[DetectionRecord]:
        """
        Run detection over a list of images.

        Args:
            images:       List of image paths (str/Path) or BGR numpy arrays.
            true_labels:  Optional list of ground-truth identity labels,
                          one per image. None entries are allowed.
            annotations:  Optional dict mapping image filename → list of GT
                          bounding boxes [[x1,y1,x2,y2],...].
                          Used for IoU-based metrics downstream.

        Returns:
            List of DetectionRecord objects, one per input image.
            Order matches the input list.
        """
        if true_labels is not None and len(true_labels) != len(images):
            raise ValueError(
                f"true_labels length ({len(true_labels)}) must match "
                f"images length ({len(images)})."
            )

        records: List[DetectionRecord] = []

        for idx, img_input in enumerate(images):
            label = true_labels[idx] if true_labels is not None else None
            record = self._process_one(idx, img_input, label, annotations)
            records.append(record)

        detected_count = sum(1 for r in records if r.detected)
        logger.info(
            "DetectionPipeline [%s]: %d/%d images with face(s) detected.",
            self._detector.name, detected_count, len(records),
        )
        return records

    def run_single(
        self,
        image: ImageInput,
        true_label: Optional[str] = None,
        gt_boxes: Optional[List[List[int]]] = None,
    ) -> DetectionRecord:
        """
        Run detection on a single image. Convenience wrapper around run().

        Args:
            image:      Image path or BGR numpy array.
            true_label: Optional ground-truth identity label.
            gt_boxes:   Optional list of GT bounding boxes.

        Returns:
            A single DetectionRecord.
        """
        ann = None
        image_id = self._make_image_id(0, image)
        if gt_boxes is not None:
            ann = {Path(image_id).name: gt_boxes}
        return self._process_one(0, image, true_label, ann)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_one(
        self,
        idx: int,
        img_input: ImageInput,
        true_label: Optional[str],
        annotations: Optional[Dict[str, List[List[int]]]],
    ) -> DetectionRecord:
        """Load, preprocess, detect, and time a single image."""
        image_id = self._make_image_id(idx, img_input)

        # --- Load image (excluded from timing) ---
        bgr = self._load(img_input, image_id)
        if bgr is None:
            return DetectionRecord(
                image_id=image_id,
                true_label=true_label,
                detections=[],
                detected=False,
                detection_ms=0.0,
                ground_truth_boxes=None,
                image_shape=None,
            )

        # --- Preprocess (excluded from timing) ---
        preprocessed = self._preprocess(bgr)
        h, w = preprocessed.shape[:2]

        # --- Detect (timed) ---
        t0 = time.perf_counter()
        try:
            detections = self._detector.detect(preprocessed)
        except Exception as exc:
            logger.warning(
                "DetectionPipeline: detector '%s' raised on image '%s': %s",
                self._detector.name, image_id, exc,
            )
            detections = []
        detection_ms = (time.perf_counter() - t0) * 1000.0

        # --- Resolve GT boxes ---
        gt_boxes = None
        if annotations:
            filename = Path(image_id).name
            gt_boxes = annotations.get(filename)

        return DetectionRecord(
            image_id=image_id,
            true_label=true_label,
            detections=detections,
            detected=len(detections) > 0,
            detection_ms=round(detection_ms, 3),
            ground_truth_boxes=gt_boxes,
            image_shape=(h, w),
        )

    def _load(self, img_input: ImageInput, image_id: str) -> Optional[np.ndarray]:
        """Load a BGR image from a path or return the array directly."""
        if isinstance(img_input, np.ndarray):
            if img_input.size == 0:
                logger.warning("DetectionPipeline: empty numpy array for '%s'.", image_id)
                return None
            return img_input

        path = Path(img_input)
        if not path.exists():
            logger.warning("DetectionPipeline: image not found: '%s'.", path)
            return None

        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if bgr is None:
            logger.warning("DetectionPipeline: cv2 could not decode '%s'.", path)
            return None
        return bgr

    def _preprocess(self, bgr: np.ndarray) -> np.ndarray:
        """Resize and clip pixel values. Returns uint8 BGR array."""
        if self._image_size is not None:
            w, h = self._image_size
            bgr = cv2.resize(bgr, (w, h), interpolation=cv2.INTER_LINEAR)
        return np.clip(bgr, 0, 255).astype(np.uint8)

    @staticmethod
    def _make_image_id(idx: int, img_input: ImageInput) -> str:
        """Generate a stable string ID for an image input."""
        if isinstance(img_input, np.ndarray):
            return f"array_{idx}"
        return str(img_input)
