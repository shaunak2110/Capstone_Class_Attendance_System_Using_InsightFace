"""
RecognitionPipeline — builds a gallery from labeled face crops, then runs
recognition over probe DetectionRecords and returns PredictionRecords.

Timing breakdown per probe image:
  - detection_ms:    carried over from DetectionRecord (already measured)
  - recognition_ms:  time for recognizer.predict() only
  - total_ms:        detection_ms + recognition_ms

Usage:
    from detection.haarcascade_detector import HaarcascadeDetector
    from recognition.lbph_recognizer import LBPHFallbackRecognizer
    from pipeline.detection_pipeline import DetectionPipeline
    from pipeline.recognition_pipeline import RecognitionPipeline

    detector  = HaarcascadeDetector()
    recognizer = LBPHFallbackRecognizer()

    det_pipeline = DetectionPipeline(detector)
    rec_pipeline = RecognitionPipeline(recognizer, threshold=0.5)

    # Build gallery
    rec_pipeline.build_gallery(gallery_pairs)   # [(label, crop), ...]

    # Run on probe images
    det_records = det_pipeline.run(probe_images, probe_labels)
    predictions = rec_pipeline.predict_probe(det_records)

    for p in predictions:
        print(p.image_id, p.true_label, p.predicted_label,
              p.similarity, p.detected, p.total_ms)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

from detection import DetectionResult
from pipeline.detection_pipeline import DetectionRecord, ImageInput
from recognition import BaseRecognizer, RecognitionResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PredictionRecord — one record per probe image
# ---------------------------------------------------------------------------

@dataclass
class PredictionRecord:
    """
    Full prediction result for a single probe image.

    Attributes:
        image_id:        String identifier matching the DetectionRecord.
        true_label:      Ground-truth identity label.
        predicted_label: Predicted identity label, or None if no face detected
                         and gallery is empty, or "unknown" in open-set mode.
        similarity:      Similarity score in [0.0, 1.0].
        detected:        True if at least one face was detected in the image.
        is_unknown:      True if the recognizer returned "unknown" (open-set).
        detection_ms:    Time for face detection (from DetectionRecord).
        recognition_ms:  Time for recognizer.predict() call only.
        total_ms:        detection_ms + recognition_ms.
        det_confidence:  Detection confidence of the face used for recognition.
                         None if no face was detected.
        bbox:            Bounding box [x1,y1,x2,y2] of the face used.
                         None if no face was detected.
    """
    image_id: str
    true_label: Optional[str]
    predicted_label: Optional[str]
    similarity: float
    detected: bool
    is_unknown: bool
    detection_ms: float
    recognition_ms: float
    total_ms: float
    det_confidence: Optional[float] = None
    bbox: Optional[List[int]] = None

    @property
    def is_correct(self) -> bool:
        """True if predicted_label matches true_label (both non-None)."""
        return (
            self.true_label is not None
            and self.predicted_label is not None
            and self.predicted_label == self.true_label
        )

    @property
    def is_missed_detection(self) -> bool:
        """True if no face was detected (counts toward FRR)."""
        return not self.detected

    def to_dict(self) -> dict:
        """Serialise to a flat dict for CSV export."""
        return {
            "image_id": self.image_id,
            "true_label": self.true_label,
            "predicted_label": self.predicted_label,
            "similarity": round(self.similarity, 6),
            "detected": self.detected,
            "is_unknown": self.is_unknown,
            "detection_ms": round(self.detection_ms, 3),
            "recognition_ms": round(self.recognition_ms, 3),
            "total_ms": round(self.total_ms, 3),
            "det_confidence": round(self.det_confidence, 4) if self.det_confidence is not None else None,
            "bbox": str(self.bbox) if self.bbox is not None else None,
        }


# ---------------------------------------------------------------------------
# RecognitionPipeline
# ---------------------------------------------------------------------------

class RecognitionPipeline:
    """
    Builds a gallery and runs recognition over probe DetectionRecords.

    Args:
        recognizer:  Any BaseRecognizer implementation.
        threshold:   Similarity threshold for open-set rejection. Default 0.5.
        open_set:    Enable open-set rejection. Default False.
        image_size:  Resize gallery crops before enrollment. Default (112, 112).
                     Set to None to skip resizing.
    """

    def __init__(
        self,
        recognizer: BaseRecognizer,
        threshold: float = 0.5,
        open_set: bool = False,
        image_size: Optional[Tuple[int, int]] = (112, 112),
    ) -> None:
        self._recognizer = recognizer
        self._threshold = threshold
        self._open_set = open_set
        self._image_size = image_size
        self._gallery_built = False

    @property
    def recognizer(self) -> BaseRecognizer:
        return self._recognizer

    @property
    def gallery_built(self) -> bool:
        return self._gallery_built

    # ------------------------------------------------------------------
    # Gallery enrollment
    # ------------------------------------------------------------------

    def build_gallery(
        self,
        pairs: List[Tuple[str, Union[np.ndarray, str, Path]]],
    ) -> None:
        """
        Enroll (identity_label, face_crop) pairs into the recognizer gallery.

        Accepts face crops as BGR numpy arrays or image paths.
        Applies optional resizing before enrollment.

        Args:
            pairs: List of (identity_label, face_crop_or_path) tuples.

        Raises:
            ValueError: If pairs is empty.
        """
        if not pairs:
            raise ValueError("build_gallery() requires at least one (label, crop) pair.")

        processed: List[Tuple[str, np.ndarray]] = []
        for label, crop_or_path in pairs:
            crop = self._load_crop(crop_or_path)
            if crop is None:
                logger.warning(
                    "RecognitionPipeline: skipping invalid crop for label '%s'.", label
                )
                continue
            if self._image_size is not None:
                crop = cv2.resize(crop, self._image_size, interpolation=cv2.INTER_LINEAR)
            processed.append((label, crop))

        if not processed:
            raise ValueError(
                "No valid crops found in gallery pairs after loading."
            )

        self._recognizer.build_gallery(processed)
        self._gallery_built = True
        logger.info(
            "RecognitionPipeline [%s]: gallery built with %d crops.",
            self._recognizer.name, len(processed),
        )

    # ------------------------------------------------------------------
    # Probe prediction
    # ------------------------------------------------------------------

    def predict_probe(
        self,
        detection_records: List[DetectionRecord],
    ) -> List[PredictionRecord]:
        """
        Run recognition over a list of DetectionRecords.

        For each record:
          - If no face detected: record as missed detection (detected=False).
          - If face(s) detected: use the highest-confidence crop for recognition.
          - Timing: recognition_ms = time for recognizer.predict() only.
                    total_ms = detection_ms + recognition_ms.

        Args:
            detection_records: Output of DetectionPipeline.run().

        Returns:
            List of PredictionRecord objects, one per DetectionRecord.
        """
        predictions: List[PredictionRecord] = []

        for record in detection_records:
            pred = self._predict_one(record)
            predictions.append(pred)

        correct = sum(1 for p in predictions if p.is_correct)
        detected = sum(1 for p in predictions if p.detected)
        logger.info(
            "RecognitionPipeline [%s]: %d/%d detected, %d/%d correct.",
            self._recognizer.name,
            detected, len(predictions),
            correct, len(predictions),
        )
        return predictions

    def predict_single(
        self,
        image: Union[np.ndarray, str, Path],
        true_label: Optional[str] = None,
        detection_ms: float = 0.0,
    ) -> PredictionRecord:
        """
        Recognize a single pre-cropped face image directly.

        Useful for quick testing without running DetectionPipeline first.

        Args:
            image:        BGR numpy array or image path of the face crop.
            true_label:   Optional ground-truth label.
            detection_ms: Optional detection time to include in total_ms.

        Returns:
            A single PredictionRecord.
        """
        crop = self._load_crop(image)
        image_id = str(image) if not isinstance(image, np.ndarray) else "array_0"

        if crop is None:
            return PredictionRecord(
                image_id=image_id,
                true_label=true_label,
                predicted_label=None,
                similarity=0.0,
                detected=False,
                is_unknown=False,
                detection_ms=detection_ms,
                recognition_ms=0.0,
                total_ms=detection_ms,
            )

        t0 = time.perf_counter()
        rec_result = self._recognizer.predict(crop, self._threshold, self._open_set)
        recognition_ms = (time.perf_counter() - t0) * 1000.0

        return PredictionRecord(
            image_id=image_id,
            true_label=true_label,
            predicted_label=rec_result.predicted_label,
            similarity=rec_result.similarity,
            detected=True,
            is_unknown=rec_result.is_unknown,
            detection_ms=detection_ms,
            recognition_ms=round(recognition_ms, 3),
            total_ms=round(detection_ms + recognition_ms, 3),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _predict_one(self, record: DetectionRecord) -> PredictionRecord:
        """Process a single DetectionRecord into a PredictionRecord."""
        # No face detected — missed detection
        if not record.detected or not record.detections:
            return PredictionRecord(
                image_id=record.image_id,
                true_label=record.true_label,
                predicted_label=None,
                similarity=0.0,
                detected=False,
                is_unknown=False,
                detection_ms=record.detection_ms,
                recognition_ms=0.0,
                total_ms=record.detection_ms,
            )

        # Use the highest-confidence detection
        best = record.best_detection
        crop = best.crop

        # Optionally resize crop before recognition
        if self._image_size is not None and crop.size > 0:
            crop = cv2.resize(crop, self._image_size, interpolation=cv2.INTER_LINEAR)

        # Run recognition (timed)
        t0 = time.perf_counter()
        try:
            rec_result = self._recognizer.predict(crop, self._threshold, self._open_set)
        except Exception as exc:
            logger.warning(
                "RecognitionPipeline: recognizer '%s' raised on '%s': %s",
                self._recognizer.name, record.image_id, exc,
            )
            rec_result = RecognitionResult(predicted_label=None, similarity=0.0)
        recognition_ms = (time.perf_counter() - t0) * 1000.0

        total_ms = record.detection_ms + recognition_ms

        return PredictionRecord(
            image_id=record.image_id,
            true_label=record.true_label,
            predicted_label=rec_result.predicted_label,
            similarity=rec_result.similarity,
            detected=True,
            is_unknown=rec_result.is_unknown,
            detection_ms=record.detection_ms,
            recognition_ms=round(recognition_ms, 3),
            total_ms=round(total_ms, 3),
            det_confidence=best.confidence,
            bbox=best.bbox,
        )

    @staticmethod
    def _load_crop(
        crop_or_path: Union[np.ndarray, str, Path],
    ) -> Optional[np.ndarray]:
        """Load a BGR crop from a numpy array or file path."""
        if isinstance(crop_or_path, np.ndarray):
            return crop_or_path if crop_or_path.size > 0 else None
        path = Path(crop_or_path)
        if not path.exists():
            return None
        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        return bgr
