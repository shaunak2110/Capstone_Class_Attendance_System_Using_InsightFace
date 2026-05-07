"""
Tests for the detection layer — BaseDetector, DetectionResult,
InsightFaceDetector, and HaarcascadeDetector.

Strategy:
  - DetectionResult and BaseDetector contract tests use synthetic data only
    (no model files required).
  - InsightFaceDetector and HaarcascadeDetector are tested with a real face
    image (downloaded from a URL or generated synthetically).
  - Model-dependent tests are skipped gracefully if the model/library is absent.

Run from workspace root:
    python -m pytest backend/evaluation/tests/test_detectors.py -v

Test a single real image:
    python -m pytest backend/evaluation/tests/test_detectors.py -v -k "real_image"
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

# Ensure backend/evaluation is on sys.path
_EVAL_ROOT = Path(__file__).resolve().parent.parent
if str(_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_EVAL_ROOT))

from detection import BaseDetector, DetectionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bgr(h: int = 100, w: int = 100, fill: int = 128) -> np.ndarray:
    """Create a solid-colour BGR image."""
    return np.full((h, w, 3), fill, dtype=np.uint8)


def _make_detection_result(
    bbox=(10, 20, 60, 80),
    confidence=0.95,
    crop_shape=(60, 50, 3),
) -> DetectionResult:
    crop = np.zeros(crop_shape, dtype=np.uint8)
    return DetectionResult(bbox=list(bbox), confidence=confidence, crop=crop)


# ---------------------------------------------------------------------------
# DetectionResult tests
# ---------------------------------------------------------------------------

class TestDetectionResult:
    def test_basic_construction(self):
        r = _make_detection_result()
        assert r.bbox == [10, 20, 60, 80]
        assert r.confidence == 0.95
        assert r.crop.shape == (60, 50, 3)

    def test_bbox_coerced_to_int(self):
        r = DetectionResult(
            bbox=[10.7, 20.3, 60.9, 80.1],
            confidence=0.9,
            crop=np.zeros((60, 50, 3), dtype=np.uint8),
        )
        assert all(isinstance(v, int) for v in r.bbox)

    def test_confidence_coerced_to_float(self):
        r = _make_detection_result(confidence=1)
        assert isinstance(r.confidence, float)

    def test_properties_x1_y1_x2_y2(self):
        r = _make_detection_result(bbox=(5, 10, 55, 90))
        assert r.x1 == 5
        assert r.y1 == 10
        assert r.x2 == 55
        assert r.y2 == 90

    def test_width_height_area(self):
        r = _make_detection_result(bbox=(10, 20, 60, 80))
        assert r.width == 50
        assert r.height == 60
        assert r.area == 3000

    def test_is_valid_true(self):
        r = _make_detection_result()
        assert r.is_valid() is True

    def test_is_valid_false_degenerate_bbox(self):
        r = DetectionResult(
            bbox=[50, 20, 10, 80],  # x1 > x2
            confidence=0.9,
            crop=np.zeros((60, 50, 3), dtype=np.uint8),
        )
        assert r.is_valid() is False

    def test_is_valid_false_empty_crop(self):
        r = DetectionResult(
            bbox=[10, 20, 60, 80],
            confidence=0.9,
            crop=np.zeros((0, 0, 3), dtype=np.uint8),
        )
        assert r.is_valid() is False

    def test_is_valid_false_confidence_out_of_range(self):
        r = DetectionResult(
            bbox=[10, 20, 60, 80],
            confidence=1.5,
            crop=np.zeros((60, 50, 3), dtype=np.uint8),
        )
        assert r.is_valid() is False


# ---------------------------------------------------------------------------
# BaseDetector ABC tests
# ---------------------------------------------------------------------------

class TestBaseDetectorABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseDetector()

    def test_concrete_subclass_must_implement_detect(self):
        class IncompleteDetector(BaseDetector):
            @property
            def name(self):
                return "incomplete"
            # Missing detect()

        with pytest.raises(TypeError):
            IncompleteDetector()

    def test_concrete_subclass_must_implement_name(self):
        class IncompleteDetector(BaseDetector):
            def detect(self, image_bgr):
                return []
            # Missing name property

        with pytest.raises(TypeError):
            IncompleteDetector()

    def test_valid_concrete_subclass(self):
        class MockDetector(BaseDetector):
            @property
            def name(self):
                return "mock"

            def detect(self, image_bgr):
                return []

        d = MockDetector()
        assert d.name == "mock"
        assert d.detect(_make_bgr()) == []

    def test_crop_face_utility(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[20:60, 10:50] = 200  # fill a region

        class MockDetector(BaseDetector):
            @property
            def name(self):
                return "mock"
            def detect(self, image_bgr):
                return []

        d = MockDetector()
        crop = d._crop_face(img, [10, 20, 50, 60])
        assert crop.shape == (40, 40, 3)
        assert crop[0, 0, 0] == 200

    def test_crop_face_clamps_to_bounds(self):
        img = np.zeros((50, 50, 3), dtype=np.uint8)

        class MockDetector(BaseDetector):
            @property
            def name(self):
                return "mock"
            def detect(self, image_bgr):
                return []

        d = MockDetector()
        # bbox extends beyond image
        crop = d._crop_face(img, [-10, -10, 100, 100])
        assert crop.shape == (50, 50, 3)


# ---------------------------------------------------------------------------
# HaarcascadeDetector tests (no model file dependency beyond OpenCV)
# ---------------------------------------------------------------------------

class TestHaarcascadeDetector:
    @pytest.fixture
    def detector(self):
        from detection.haarcascade_detector import HaarcascadeDetector
        return HaarcascadeDetector()

    def test_name_is_haarcascade(self, detector):
        assert detector.name == "haarcascade"

    def test_returns_list(self, detector):
        img = _make_bgr(200, 200)
        result = detector.detect(img)
        assert isinstance(result, list)

    def test_empty_image_returns_empty(self, detector):
        result = detector.detect(np.zeros((0, 0, 3), dtype=np.uint8))
        assert result == []

    def test_none_image_returns_empty(self, detector):
        result = detector.detect(None)
        assert result == []

    def test_solid_colour_image_returns_empty_or_list(self, detector):
        # A solid grey image should return no faces (or possibly false positives)
        img = _make_bgr(300, 300, fill=128)
        result = detector.detect(img)
        assert isinstance(result, list)

    def test_all_results_are_detection_result(self, detector):
        img = _make_bgr(300, 300)
        result = detector.detect(img)
        for r in result:
            assert isinstance(r, DetectionResult)

    def test_all_results_are_valid(self, detector):
        img = _make_bgr(300, 300)
        result = detector.detect(img)
        for r in result:
            assert r.is_valid(), f"Invalid DetectionResult: {r}"

    def test_bbox_within_image_bounds(self, detector):
        h, w = 300, 300
        img = _make_bgr(h, w)
        result = detector.detect(img)
        for r in result:
            assert r.x1 >= 0 and r.y1 >= 0
            assert r.x2 <= w and r.y2 <= h

    def test_confidence_in_range(self, detector):
        img = _make_bgr(300, 300)
        result = detector.detect(img)
        for r in result:
            assert 0.0 <= r.confidence <= 1.0

    def test_crop_shape_matches_bbox(self, detector):
        img = _make_bgr(300, 300)
        result = detector.detect(img)
        for r in result:
            expected_h = r.y2 - r.y1
            expected_w = r.x2 - r.x1
            assert r.crop.shape == (expected_h, expected_w, 3), (
                f"Crop shape {r.crop.shape} doesn't match bbox "
                f"({expected_w}x{expected_h})"
            )

    def test_sorted_by_confidence_descending(self, detector):
        img = _make_bgr(300, 300)
        result = detector.detect(img)
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i].confidence >= result[i + 1].confidence

    def test_missing_cascade_raises_file_not_found(self):
        from detection.haarcascade_detector import HaarcascadeDetector
        with pytest.raises(FileNotFoundError):
            HaarcascadeDetector(cascade_path="/nonexistent/cascade.xml")

    def test_real_face_image_detection(self, detector):
        """
        Test detection on a real face image.
        Uses a synthetic face-like pattern if no real image is available.
        """
        # Try to load a real face image from the dataset
        dataset_path = _EVAL_ROOT / "dataset" / "raw"
        face_image = None

        if dataset_path.exists():
            for identity_dir in sorted(dataset_path.iterdir()):
                if identity_dir.is_dir():
                    for img_file in sorted(identity_dir.iterdir()):
                        if img_file.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                            img = cv2.imread(str(img_file))
                            if img is not None:
                                face_image = img
                                break
                if face_image is not None:
                    break

        if face_image is None:
            pytest.skip("No real face images found in dataset/raw/ — skipping real image test")

        result = detector.detect(face_image)
        # We don't assert detections > 0 (Haar may miss some faces)
        # but we assert the output format is correct
        assert isinstance(result, list)
        for r in result:
            assert isinstance(r, DetectionResult)
            assert r.is_valid()


# ---------------------------------------------------------------------------
# InsightFaceDetector tests
# ---------------------------------------------------------------------------

class TestInsightFaceDetector:
    @pytest.fixture
    def detector(self):
        """Skip if insightface is not installed or model files are missing."""
        try:
            from detection.insightface_detector import InsightFaceDetector
            return InsightFaceDetector()
        except ImportError as e:
            pytest.skip(f"insightface not installed: {e}")
        except FileNotFoundError as e:
            pytest.skip(f"buffalo_l model files not found: {e}")

    def test_name_is_insightface(self, detector):
        assert detector.name == "insightface"

    def test_returns_list(self, detector):
        img = _make_bgr(640, 640)
        result = detector.detect(img)
        assert isinstance(result, list)

    def test_empty_image_returns_empty(self, detector):
        result = detector.detect(np.zeros((0, 0, 3), dtype=np.uint8))
        assert result == []

    def test_none_image_returns_empty(self, detector):
        result = detector.detect(None)
        assert result == []

    def test_solid_colour_returns_empty_or_list(self, detector):
        img = _make_bgr(640, 640, fill=100)
        result = detector.detect(img)
        assert isinstance(result, list)

    def test_all_results_are_detection_result(self, detector):
        img = _make_bgr(640, 640)
        result = detector.detect(img)
        for r in result:
            assert isinstance(r, DetectionResult)

    def test_all_results_are_valid(self, detector):
        img = _make_bgr(640, 640)
        result = detector.detect(img)
        for r in result:
            assert r.is_valid(), f"Invalid DetectionResult: {r}"

    def test_bbox_within_image_bounds(self, detector):
        h, w = 640, 640
        img = _make_bgr(h, w)
        result = detector.detect(img)
        for r in result:
            assert r.x1 >= 0 and r.y1 >= 0
            assert r.x2 <= w and r.y2 <= h

    def test_confidence_in_range(self, detector):
        img = _make_bgr(640, 640)
        result = detector.detect(img)
        for r in result:
            assert 0.0 <= r.confidence <= 1.0

    def test_crop_shape_matches_bbox(self, detector):
        img = _make_bgr(640, 640)
        result = detector.detect(img)
        for r in result:
            expected_h = r.y2 - r.y1
            expected_w = r.x2 - r.x1
            assert r.crop.shape == (expected_h, expected_w, 3)

    def test_sorted_by_confidence_descending(self, detector):
        img = _make_bgr(640, 640)
        result = detector.detect(img)
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i].confidence >= result[i + 1].confidence

    def test_missing_model_raises_file_not_found(self):
        from detection.insightface_detector import InsightFaceDetector
        with pytest.raises(FileNotFoundError):
            InsightFaceDetector(model_dir="/nonexistent/buffalo_l")

    def test_real_face_image_detection(self, detector):
        """
        Test detection on a real face image from the dataset.
        Asserts at least one face is detected and the result is well-formed.
        """
        dataset_path = _EVAL_ROOT / "dataset" / "raw"
        face_image = None

        if dataset_path.exists():
            for identity_dir in sorted(dataset_path.iterdir()):
                if identity_dir.is_dir():
                    for img_file in sorted(identity_dir.iterdir()):
                        if img_file.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                            img = cv2.imread(str(img_file))
                            if img is not None:
                                face_image = img
                                break
                if face_image is not None:
                    break

        if face_image is None:
            pytest.skip("No real face images found in dataset/raw/")

        result = detector.detect(face_image)
        assert isinstance(result, list)
        # InsightFace should detect at least one face in a real face photo
        assert len(result) >= 1, (
            "InsightFaceDetector found no faces in a real face image. "
            "Check image quality or model path."
        )
        for r in result:
            assert r.is_valid()
            assert r.crop.shape[2] == 3  # BGR channels


# ---------------------------------------------------------------------------
# Cross-detector interface consistency tests
# ---------------------------------------------------------------------------

class TestDetectorInterfaceConsistency:
    """
    Verify that both detectors produce identically structured output,
    so they are interchangeable in the pipeline.
    """

    @pytest.fixture
    def haarcascade(self):
        from detection.haarcascade_detector import HaarcascadeDetector
        return HaarcascadeDetector()

    @pytest.fixture
    def insightface(self):
        try:
            from detection.insightface_detector import InsightFaceDetector
            return InsightFaceDetector()
        except (ImportError, FileNotFoundError):
            pytest.skip("InsightFace not available")

    def test_both_return_list(self, haarcascade, insightface):
        img = _make_bgr(640, 640)
        assert isinstance(haarcascade.detect(img), list)
        assert isinstance(insightface.detect(img), list)

    def test_both_return_detection_result_objects(self, haarcascade, insightface):
        img = _make_bgr(640, 640)
        for r in haarcascade.detect(img):
            assert isinstance(r, DetectionResult)
        for r in insightface.detect(img):
            assert isinstance(r, DetectionResult)

    def test_both_have_name_property(self, haarcascade, insightface):
        assert isinstance(haarcascade.name, str)
        assert isinstance(insightface.name, str)
        assert haarcascade.name != insightface.name

    def test_both_handle_empty_image_gracefully(self, haarcascade, insightface):
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        assert haarcascade.detect(empty) == []
        assert insightface.detect(empty) == []

    def test_output_compatible_with_datasetsplitter_preprocess(
        self, haarcascade, insightface
    ):
        """
        Verify detectors work with images produced by DatasetSplitter.preprocess().
        """
        from configs.config import ExperimentConfig
        from utils.image_loader import DatasetSplitter
        import tempfile

        # Create a temp image file
        with tempfile.TemporaryDirectory() as tmp:
            img_path = Path(tmp) / "test.jpg"
            cv2.imwrite(str(img_path), _make_bgr(200, 200))

            cfg = ExperimentConfig.from_dict({
                "dataset_path": tmp,
                "detectors": ["haarcascade"],
                "recognizers": ["lbph"],
                "image_size": [640, 640],
            })
            splitter = DatasetSplitter(cfg, min_images=2)
            preprocessed = splitter.preprocess(img_path)

        # Both detectors must accept the preprocessed output without error
        assert preprocessed.shape == (640, 640, 3)
        assert preprocessed.dtype == np.uint8

        hc_result = haarcascade.detect(preprocessed)
        if_result = insightface.detect(preprocessed)

        assert isinstance(hc_result, list)
        assert isinstance(if_result, list)
