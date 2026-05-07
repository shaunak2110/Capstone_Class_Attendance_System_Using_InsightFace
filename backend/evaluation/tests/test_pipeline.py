"""
Tests for DetectionPipeline and RecognitionPipeline.

Strategy:
  - All tests use mock detectors/recognizers or HaarcascadeDetector +
    LBPHFallbackRecognizer — no heavy model dependencies required.
  - Real-image end-to-end tests load from dataset/raw/ if available.
  - InsightFace pipeline tests are skipped if model files are absent.

Run from workspace root:
    python -m pytest backend/evaluation/tests/test_pipeline.py -v
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest

_EVAL_ROOT = Path(__file__).resolve().parent.parent
if str(_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_EVAL_ROOT))

from detection import BaseDetector, DetectionResult
from recognition import BaseRecognizer, RecognitionResult
from pipeline.detection_pipeline import DetectionPipeline, DetectionRecord
from pipeline.recognition_pipeline import RecognitionPipeline, PredictionRecord


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _bgr(h: int = 100, w: int = 100, fill: int = 128) -> np.ndarray:
    return np.full((h, w, 3), fill, dtype=np.uint8)


def _make_crop(h: int = 50, w: int = 50, fill: int = 150) -> np.ndarray:
    return np.full((h, w, 3), fill, dtype=np.uint8)


class MockDetector(BaseDetector):
    """Detector that returns a configurable list of DetectionResults."""

    def __init__(self, results: Optional[List[DetectionResult]] = None):
        self._results = results or []

    @property
    def name(self) -> str:
        return "mock_detector"

    def detect(self, image_bgr: np.ndarray) -> List[DetectionResult]:
        if image_bgr is None or image_bgr.size == 0:
            return []
        return list(self._results)


class MockRecognizer(BaseRecognizer):
    """Recognizer that returns a configurable RecognitionResult."""

    def __init__(self, result: Optional[RecognitionResult] = None):
        self._result = result or RecognitionResult("mock_id", 0.9)
        self._gallery_built = False

    @property
    def name(self) -> str:
        return "mock_recognizer"

    def build_gallery(self, pairs):
        if not pairs:
            raise ValueError("Empty pairs")
        self._gallery_built = True

    def predict(self, face_crop, threshold=0.5, open_set=False):
        if not self._gallery_built:
            return RecognitionResult(None, 0.0)
        return self._result


def _make_detection_result(
    bbox=(10, 10, 60, 60), confidence=0.9, fill=150
) -> DetectionResult:
    crop = _make_crop(fill=fill)
    return DetectionResult(bbox=list(bbox), confidence=confidence, crop=crop)


def _make_detection_record(
    image_id="test.jpg",
    true_label="alice",
    detections=None,
    detection_ms=5.0,
) -> DetectionRecord:
    dets = detections if detections is not None else [_make_detection_result()]
    return DetectionRecord(
        image_id=image_id,
        true_label=true_label,
        detections=dets,
        detected=len(dets) > 0,
        detection_ms=detection_ms,
        image_shape=(100, 100),
    )


# ---------------------------------------------------------------------------
# DetectionPipeline tests
# ---------------------------------------------------------------------------

class TestDetectionPipeline:
    @pytest.fixture
    def pipeline(self):
        return DetectionPipeline(MockDetector([_make_detection_result()]))

    @pytest.fixture
    def empty_pipeline(self):
        return DetectionPipeline(MockDetector([]))

    def test_returns_list_of_detection_records(self, pipeline):
        records = pipeline.run([_bgr()])
        assert isinstance(records, list)
        assert all(isinstance(r, DetectionRecord) for r in records)

    def test_one_record_per_image(self, pipeline):
        images = [_bgr(), _bgr(), _bgr()]
        records = pipeline.run(images)
        assert len(records) == len(images)

    def test_detected_true_when_faces_found(self, pipeline):
        records = pipeline.run([_bgr()])
        assert records[0].detected is True

    def test_detected_false_when_no_faces(self, empty_pipeline):
        records = empty_pipeline.run([_bgr()])
        assert records[0].detected is False
        assert records[0].detections == []

    def test_true_labels_assigned(self, pipeline):
        records = pipeline.run([_bgr(), _bgr()], true_labels=["alice", "bob"])
        assert records[0].true_label == "alice"
        assert records[1].true_label == "bob"

    def test_true_labels_none_when_not_provided(self, pipeline):
        records = pipeline.run([_bgr()])
        assert records[0].true_label is None

    def test_detection_ms_is_non_negative(self, pipeline):
        records = pipeline.run([_bgr()])
        assert records[0].detection_ms >= 0.0

    def test_image_shape_recorded(self, pipeline):
        records = pipeline.run([_bgr(200, 300)])
        # After preprocessing to (640,640), shape should be (640, 640)
        assert records[0].image_shape == (640, 640)

    def test_empty_numpy_array_returns_no_detection(self, pipeline):
        records = pipeline.run([np.zeros((0, 0, 3), dtype=np.uint8)])
        assert records[0].detected is False

    def test_missing_file_returns_no_detection(self, pipeline):
        records = pipeline.run(["/nonexistent/path/image.jpg"])
        assert records[0].detected is False

    def test_mismatched_labels_raises(self, pipeline):
        with pytest.raises(ValueError, match="true_labels length"):
            pipeline.run([_bgr(), _bgr()], true_labels=["alice"])

    def test_image_id_from_path(self, pipeline, tmp_path):
        img_path = tmp_path / "test.jpg"
        cv2.imwrite(str(img_path), _bgr())
        records = pipeline.run([str(img_path)])
        assert records[0].image_id == str(img_path)

    def test_image_id_from_array(self, pipeline):
        records = pipeline.run([_bgr()])
        assert records[0].image_id == "array_0"

    def test_annotations_attached_to_record(self, pipeline, tmp_path):
        img_path = tmp_path / "face.jpg"
        cv2.imwrite(str(img_path), _bgr())
        ann = {"face.jpg": [[10, 10, 60, 60]]}
        records = pipeline.run([str(img_path)], annotations=ann)
        assert records[0].ground_truth_boxes == [[10, 10, 60, 60]]

    def test_run_single_convenience(self, pipeline):
        record = pipeline.run_single(_bgr(), true_label="alice")
        assert isinstance(record, DetectionRecord)
        assert record.true_label == "alice"

    def test_best_detection_returns_highest_confidence(self):
        d1 = _make_detection_result(confidence=0.7)
        d2 = _make_detection_result(confidence=0.95)
        d3 = _make_detection_result(confidence=0.5)
        pipeline = DetectionPipeline(MockDetector([d1, d2, d3]))
        records = pipeline.run([_bgr()])
        assert records[0].best_detection.confidence == 0.95

    def test_no_resize_when_image_size_none(self):
        pipeline = DetectionPipeline(MockDetector([_make_detection_result()]), image_size=None)
        records = pipeline.run([_bgr(200, 300)])
        assert records[0].image_shape == (200, 300)

    def test_detector_is_interchangeable(self):
        """Swapping the detector changes results without changing pipeline code."""
        det_with_face = DetectionPipeline(MockDetector([_make_detection_result()]))
        det_without_face = DetectionPipeline(MockDetector([]))
        img = _bgr()
        assert det_with_face.run([img])[0].detected is True
        assert det_without_face.run([img])[0].detected is False


# ---------------------------------------------------------------------------
# RecognitionPipeline tests
# ---------------------------------------------------------------------------

class TestRecognitionPipeline:
    @pytest.fixture
    def rec_pipeline(self):
        rec = MockRecognizer(RecognitionResult("alice", 0.85))
        pipeline = RecognitionPipeline(rec, threshold=0.5)
        pipeline.build_gallery([("alice", _make_crop())])
        return pipeline

    @pytest.fixture
    def empty_rec_pipeline(self):
        """Pipeline with gallery not yet built."""
        rec = MockRecognizer()
        return RecognitionPipeline(rec, threshold=0.5)

    def test_returns_list_of_prediction_records(self, rec_pipeline):
        records = [_make_detection_record()]
        preds = rec_pipeline.predict_probe(records)
        assert isinstance(preds, list)
        assert all(isinstance(p, PredictionRecord) for p in preds)

    def test_one_prediction_per_detection_record(self, rec_pipeline):
        records = [_make_detection_record(), _make_detection_record("img2.jpg", "bob")]
        preds = rec_pipeline.predict_probe(records)
        assert len(preds) == 2

    def test_predicted_label_set(self, rec_pipeline):
        preds = rec_pipeline.predict_probe([_make_detection_record()])
        assert preds[0].predicted_label == "alice"

    def test_similarity_in_range(self, rec_pipeline):
        preds = rec_pipeline.predict_probe([_make_detection_record()])
        assert 0.0 <= preds[0].similarity <= 1.0

    def test_detected_true_when_face_found(self, rec_pipeline):
        preds = rec_pipeline.predict_probe([_make_detection_record()])
        assert preds[0].detected is True

    def test_detected_false_when_no_face(self, rec_pipeline):
        no_face = _make_detection_record(detections=[])
        preds = rec_pipeline.predict_probe([no_face])
        assert preds[0].detected is False
        assert preds[0].predicted_label is None

    def test_missed_detection_has_zero_recognition_ms(self, rec_pipeline):
        no_face = _make_detection_record(detections=[])
        preds = rec_pipeline.predict_probe([no_face])
        assert preds[0].recognition_ms == 0.0

    def test_total_ms_equals_detection_plus_recognition(self, rec_pipeline):
        record = _make_detection_record(detection_ms=10.0)
        preds = rec_pipeline.predict_probe([record])
        p = preds[0]
        assert abs(p.total_ms - (p.detection_ms + p.recognition_ms)) < 0.1

    def test_detection_ms_carried_from_record(self, rec_pipeline):
        record = _make_detection_record(detection_ms=7.5)
        preds = rec_pipeline.predict_probe([record])
        assert preds[0].detection_ms == 7.5

    def test_recognition_ms_is_non_negative(self, rec_pipeline):
        preds = rec_pipeline.predict_probe([_make_detection_record()])
        assert preds[0].recognition_ms >= 0.0

    def test_bbox_from_best_detection(self, rec_pipeline):
        det = _make_detection_result(bbox=(5, 10, 55, 90))
        record = _make_detection_record(detections=[det])
        preds = rec_pipeline.predict_probe([record])
        assert preds[0].bbox == [5, 10, 55, 90]

    def test_det_confidence_from_best_detection(self, rec_pipeline):
        det = _make_detection_result(confidence=0.88)
        record = _make_detection_record(detections=[det])
        preds = rec_pipeline.predict_probe([record])
        assert abs(preds[0].det_confidence - 0.88) < 0.01

    def test_is_correct_true_when_labels_match(self, rec_pipeline):
        record = _make_detection_record(true_label="alice")
        preds = rec_pipeline.predict_probe([record])
        assert preds[0].is_correct is True

    def test_is_correct_false_when_labels_differ(self):
        rec = MockRecognizer(RecognitionResult("bob", 0.7))
        pipeline = RecognitionPipeline(rec)
        pipeline.build_gallery([("bob", _make_crop())])
        record = _make_detection_record(true_label="alice")
        preds = pipeline.predict_probe([record])
        assert preds[0].is_correct is False

    def test_is_missed_detection_true_when_no_face(self, rec_pipeline):
        no_face = _make_detection_record(detections=[])
        preds = rec_pipeline.predict_probe([no_face])
        assert preds[0].is_missed_detection is True

    def test_open_set_unknown_label(self):
        rec = MockRecognizer(RecognitionResult("unknown", 0.1, is_unknown=True))
        pipeline = RecognitionPipeline(rec, threshold=0.5, open_set=True)
        pipeline.build_gallery([("alice", _make_crop())])
        preds = pipeline.predict_probe([_make_detection_record()])
        assert preds[0].is_unknown is True
        assert preds[0].predicted_label == "unknown"

    def test_build_gallery_empty_raises(self):
        rec = MockRecognizer()
        pipeline = RecognitionPipeline(rec)
        with pytest.raises(ValueError):
            pipeline.build_gallery([])

    def test_recognizer_is_interchangeable(self):
        """Swapping the recognizer changes predictions without changing pipeline code."""
        rec_a = MockRecognizer(RecognitionResult("alice", 0.9))
        rec_b = MockRecognizer(RecognitionResult("bob", 0.8))
        for rec, expected in [(rec_a, "alice"), (rec_b, "bob")]:
            pipeline = RecognitionPipeline(rec)
            pipeline.build_gallery([(expected, _make_crop())])
            preds = pipeline.predict_probe([_make_detection_record()])
            assert preds[0].predicted_label == expected

    def test_predict_single_convenience(self, rec_pipeline):
        result = rec_pipeline.predict_single(_make_crop(), true_label="alice")
        assert isinstance(result, PredictionRecord)
        assert result.detected is True

    def test_to_dict_has_required_keys(self, rec_pipeline):
        preds = rec_pipeline.predict_probe([_make_detection_record()])
        d = preds[0].to_dict()
        required = {
            "image_id", "true_label", "predicted_label", "similarity",
            "detected", "is_unknown", "detection_ms", "recognition_ms", "total_ms",
        }
        assert required.issubset(d.keys())


# ---------------------------------------------------------------------------
# End-to-end pipeline tests (HaarcascadeDetector + LBPHFallbackRecognizer)
# ---------------------------------------------------------------------------

class TestEndToEndPipeline:
    @pytest.fixture
    def haarcascade(self):
        from detection.haarcascade_detector import HaarcascadeDetector
        return HaarcascadeDetector()

    @pytest.fixture
    def lbph(self):
        try:
            from recognition.lbph_recognizer import LBPHRecognizer
            return LBPHRecognizer()
        except ImportError:
            from recognition.lbph_recognizer import LBPHFallbackRecognizer
            return LBPHFallbackRecognizer()

    def test_end_to_end_synthetic_image(self, haarcascade, lbph):
        """Full pipeline on a synthetic image — verifies structure, not accuracy."""
        det_pipeline = DetectionPipeline(haarcascade)
        rec_pipeline = RecognitionPipeline(lbph, threshold=0.3)

        # Build gallery with synthetic crops
        gallery_crop = _make_crop(fill=100)
        rec_pipeline.build_gallery([("alice", gallery_crop)])

        # Run detection
        img = _bgr(300, 300)
        det_records = det_pipeline.run([img], true_labels=["alice"])

        # Run recognition
        preds = rec_pipeline.predict_probe(det_records)

        assert len(preds) == 1
        p = preds[0]
        assert isinstance(p, PredictionRecord)
        assert p.true_label == "alice"
        assert p.total_ms >= 0.0
        assert p.detection_ms >= 0.0
        assert p.recognition_ms >= 0.0
        assert abs(p.total_ms - (p.detection_ms + p.recognition_ms)) < 1.0

    def test_empty_image_handled_gracefully(self, haarcascade, lbph):
        det_pipeline = DetectionPipeline(haarcascade)
        rec_pipeline = RecognitionPipeline(lbph)
        rec_pipeline.build_gallery([("alice", _make_crop())])

        det_records = det_pipeline.run([np.zeros((0, 0, 3), dtype=np.uint8)])
        preds = rec_pipeline.predict_probe(det_records)

        assert len(preds) == 1
        assert preds[0].detected is False
        assert preds[0].predicted_label is None

    def test_multiple_images_batch(self, haarcascade, lbph):
        det_pipeline = DetectionPipeline(haarcascade)
        rec_pipeline = RecognitionPipeline(lbph)
        rec_pipeline.build_gallery([("alice", _make_crop(fill=100)), ("bob", _make_crop(fill=200))])

        images = [_bgr(300, 300), _bgr(200, 200), _bgr(400, 400)]
        labels = ["alice", "bob", "alice"]

        det_records = det_pipeline.run(images, true_labels=labels)
        preds = rec_pipeline.predict_probe(det_records)

        assert len(preds) == 3
        for p in preds:
            assert isinstance(p, PredictionRecord)
            assert 0.0 <= p.similarity <= 1.0
            assert p.total_ms >= 0.0

    def test_real_face_image_end_to_end(self, haarcascade, lbph):
        """
        Full pipeline on real face images from dataset/raw/.
        Verifies output structure and timing — not recognition accuracy.
        """
        dataset_path = _EVAL_ROOT / "dataset" / "raw"
        if not dataset_path.exists():
            pytest.skip("No dataset found at dataset/raw/")

        gallery_pairs = []
        probe_images = []
        probe_labels = []

        for identity_dir in sorted(dataset_path.iterdir()):
            if not identity_dir.is_dir():
                continue
            images = sorted(
                p for p in identity_dir.iterdir()
                if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
            )
            if len(images) < 2:
                continue
            label = identity_dir.name
            # Gallery: first image; probe: second image
            crop = cv2.imread(str(images[0]))
            if crop is not None:
                gallery_pairs.append((label, crop))
            probe_img = cv2.imread(str(images[1]))
            if probe_img is not None:
                probe_images.append(probe_img)
                probe_labels.append(label)

        if not gallery_pairs or not probe_images:
            pytest.skip("Not enough images in dataset/raw/")

        det_pipeline = DetectionPipeline(haarcascade)
        rec_pipeline = RecognitionPipeline(lbph, threshold=0.3)
        rec_pipeline.build_gallery(gallery_pairs)

        det_records = det_pipeline.run(probe_images[:3], true_labels=probe_labels[:3])
        preds = rec_pipeline.predict_probe(det_records)

        assert len(preds) == len(probe_images[:3])
        for p in preds:
            assert isinstance(p, PredictionRecord)
            assert p.total_ms >= 0.0
            assert 0.0 <= p.similarity <= 1.0
            # Print for inspection
            print(
                f"\n[Pipeline] {p.true_label} → {p.predicted_label} "
                f"(sim={p.similarity:.3f}, det={p.detection_ms:.1f}ms, "
                f"rec={p.recognition_ms:.1f}ms, total={p.total_ms:.1f}ms)"
            )


# ---------------------------------------------------------------------------
# InsightFace end-to-end pipeline test
# ---------------------------------------------------------------------------

class TestInsightFacePipeline:
    @pytest.fixture
    def insightface_det(self):
        try:
            from detection.insightface_detector import InsightFaceDetector
            return InsightFaceDetector()
        except (ImportError, FileNotFoundError) as e:
            pytest.skip(f"InsightFace detector not available: {e}")

    @pytest.fixture
    def insightface_rec(self):
        try:
            from recognition.insightface_recognizer import InsightFaceRecognizer
            return InsightFaceRecognizer()
        except (ImportError, FileNotFoundError) as e:
            pytest.skip(f"InsightFace recognizer not available: {e}")

    def test_insightface_pipeline_real_images(self, insightface_det, insightface_rec):
        dataset_path = _EVAL_ROOT / "dataset" / "raw"
        if not dataset_path.exists():
            pytest.skip("No dataset found at dataset/raw/")

        gallery_pairs = []
        probe_images = []
        probe_labels = []

        for identity_dir in sorted(dataset_path.iterdir()):
            if not identity_dir.is_dir():
                continue
            images = sorted(
                p for p in identity_dir.iterdir()
                if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
            )
            if len(images) < 2:
                continue
            label = identity_dir.name
            crop = cv2.imread(str(images[0]))
            if crop is not None:
                gallery_pairs.append((label, crop))
            probe_img = cv2.imread(str(images[1]))
            if probe_img is not None:
                probe_images.append(probe_img)
                probe_labels.append(label)

        if not gallery_pairs or not probe_images:
            pytest.skip("Not enough images in dataset/raw/")

        det_pipeline = DetectionPipeline(insightface_det)
        rec_pipeline = RecognitionPipeline(insightface_rec, threshold=0.45)
        rec_pipeline.build_gallery(gallery_pairs)

        det_records = det_pipeline.run(probe_images[:2], true_labels=probe_labels[:2])
        preds = rec_pipeline.predict_probe(det_records)

        assert len(preds) == len(probe_images[:2])
        for p in preds:
            assert isinstance(p, PredictionRecord)
            assert p.total_ms >= 0.0
            print(
                f"\n[InsightFace Pipeline] {p.true_label} → {p.predicted_label} "
                f"(sim={p.similarity:.4f}, total={p.total_ms:.1f}ms)"
            )
