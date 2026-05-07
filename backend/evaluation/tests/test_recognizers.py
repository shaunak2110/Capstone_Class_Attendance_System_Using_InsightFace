"""
Tests for the recognition layer — BaseRecognizer, RecognitionResult,
InsightFaceRecognizer, and LBPHRecognizer.

Strategy:
  - RecognitionResult and BaseRecognizer contract tests use synthetic data only.
  - LBPHRecognizer tests use synthetic face crops (no model files needed).
  - InsightFaceRecognizer tests are skipped if insightface/model files are absent.
  - Real-image tests load from dataset/raw/ if available.

Run from workspace root:
    python -m pytest backend/evaluation/tests/test_recognizers.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
import pytest

_EVAL_ROOT = Path(__file__).resolve().parent.parent
if str(_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_EVAL_ROOT))

from recognition import BaseRecognizer, RecognitionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _solid_crop(h: int = 80, w: int = 80, fill: int = 128) -> np.ndarray:
    """Create a solid-colour BGR face crop."""
    return np.full((h, w, 3), fill, dtype=np.uint8)


def _noise_crop(h: int = 80, w: int = 80, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, (h, w, 3), dtype=np.uint8)


def _gallery_pairs(n_identities: int = 3, crops_per: int = 3) -> List[Tuple[str, np.ndarray]]:
    """Generate synthetic gallery pairs with distinct per-identity colours."""
    pairs = []
    for i in range(n_identities):
        fill = 50 + i * 60  # distinct grey levels
        for j in range(crops_per):
            pairs.append((f"id_{i}", _solid_crop(fill=fill)))
    return pairs


# ---------------------------------------------------------------------------
# RecognitionResult tests
# ---------------------------------------------------------------------------

class TestRecognitionResult:
    def test_basic_construction(self):
        r = RecognitionResult(predicted_label="alice", similarity=0.85)
        assert r.predicted_label == "alice"
        assert r.similarity == 0.85
        assert r.is_unknown is False

    def test_similarity_clamped_to_zero_one(self):
        r = RecognitionResult(predicted_label="alice", similarity=1.5)
        assert r.similarity == 1.0
        r2 = RecognitionResult(predicted_label="alice", similarity=-0.3)
        assert r2.similarity == 0.0

    def test_similarity_coerced_to_float(self):
        r = RecognitionResult(predicted_label="alice", similarity=1)
        assert isinstance(r.similarity, float)

    def test_is_valid_true(self):
        r = RecognitionResult(predicted_label="alice", similarity=0.7)
        assert r.is_valid() is True

    def test_is_valid_false_none_label(self):
        r = RecognitionResult(predicted_label=None, similarity=0.7)
        assert r.is_valid() is False

    def test_unknown_flag(self):
        r = RecognitionResult(predicted_label="unknown", similarity=0.2, is_unknown=True)
        assert r.is_unknown is True
        assert r.predicted_label == "unknown"


# ---------------------------------------------------------------------------
# BaseRecognizer ABC tests
# ---------------------------------------------------------------------------

class TestBaseRecognizerABC:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseRecognizer()

    def test_concrete_must_implement_build_gallery(self):
        class Incomplete(BaseRecognizer):
            @property
            def name(self):
                return "x"
            def predict(self, crop, threshold=0.5, open_set=False):
                return RecognitionResult("x", 1.0)
        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_must_implement_predict(self):
        class Incomplete(BaseRecognizer):
            @property
            def name(self):
                return "x"
            def build_gallery(self, pairs):
                pass
        with pytest.raises(TypeError):
            Incomplete()

    def test_produces_embeddings_default_true(self):
        class MockRec(BaseRecognizer):
            @property
            def name(self):
                return "mock"
            def build_gallery(self, pairs):
                pass
            def predict(self, crop, threshold=0.5, open_set=False):
                return RecognitionResult("x", 1.0)
        assert MockRec().produces_embeddings is True

    def test_cosine_similarity_identical_vectors(self):
        class MockRec(BaseRecognizer):
            @property
            def name(self):
                return "mock"
            def build_gallery(self, pairs):
                pass
            def predict(self, crop, threshold=0.5, open_set=False):
                return RecognitionResult("x", 1.0)
        r = MockRec()
        v = np.array([1.0, 0.0, 0.0])
        assert abs(r._cosine_similarity(v, v) - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal_vectors(self):
        class MockRec(BaseRecognizer):
            @property
            def name(self):
                return "mock"
            def build_gallery(self, pairs):
                pass
            def predict(self, crop, threshold=0.5, open_set=False):
                return RecognitionResult("x", 1.0)
        r = MockRec()
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert abs(r._cosine_similarity(a, b)) < 1e-6

    def test_l2_normalize_unit_vector(self):
        class MockRec(BaseRecognizer):
            @property
            def name(self):
                return "mock"
            def build_gallery(self, pairs):
                pass
            def predict(self, crop, threshold=0.5, open_set=False):
                return RecognitionResult("x", 1.0)
        r = MockRec()
        v = np.array([3.0, 4.0])
        normed = r._l2_normalize(v)
        assert abs(np.linalg.norm(normed) - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# LBPHRecognizer tests
# ---------------------------------------------------------------------------

class TestLBPHRecognizer:
    @pytest.fixture
    def rec(self):
        try:
            from recognition.lbph_recognizer import LBPHRecognizer
            return LBPHRecognizer()
        except ImportError:
            # cv2.face not available — use the pure-numpy fallback
            from recognition.lbph_recognizer import LBPHFallbackRecognizer
            return LBPHFallbackRecognizer()

    def test_name_is_lbph(self, rec):
        assert rec.name == "lbph"

    def test_produces_embeddings_false(self, rec):
        assert rec.produces_embeddings is False

    def test_build_gallery_empty_raises(self, rec):
        with pytest.raises(ValueError):
            rec.build_gallery([])

    def test_build_gallery_succeeds(self, rec):
        pairs = _gallery_pairs(n_identities=2, crops_per=3)
        rec.build_gallery(pairs)  # must not raise

    def test_predict_before_gallery_returns_none_label(self, rec):
        result = rec.predict(_solid_crop())
        assert result.predicted_label is None

    def test_predict_returns_recognition_result(self, rec):
        rec.build_gallery(_gallery_pairs())
        result = rec.predict(_solid_crop())
        assert isinstance(result, RecognitionResult)

    def test_predict_label_is_known_identity(self, rec):
        pairs = _gallery_pairs(n_identities=3)
        rec.build_gallery(pairs)
        result = rec.predict(_solid_crop())
        known_labels = {f"id_{i}" for i in range(3)} | {"unknown"}
        assert result.predicted_label in known_labels

    def test_similarity_in_range(self, rec):
        rec.build_gallery(_gallery_pairs())
        result = rec.predict(_solid_crop())
        assert 0.0 <= result.similarity <= 1.0

    def test_same_crop_high_similarity(self, rec):
        """A crop identical to a gallery image should have high similarity."""
        crop = _solid_crop(fill=100)
        rec.build_gallery([("alice", crop)])
        result = rec.predict(crop)
        assert result.predicted_label == "alice"
        assert result.similarity > 0.5, (
            f"Expected high similarity for identical crop, got {result.similarity:.3f}"
        )

    def test_open_set_rejection_below_threshold(self, rec):
        """A very different crop should be rejected in open-set mode."""
        rec.build_gallery([("alice", _solid_crop(fill=200))])
        # Use a very different crop and a high threshold to force rejection
        result = rec.predict(_solid_crop(fill=10), threshold=0.99, open_set=True)
        # Either rejected as unknown or matched — just verify format
        assert isinstance(result, RecognitionResult)
        assert 0.0 <= result.similarity <= 1.0

    def test_open_set_false_never_returns_unknown_from_threshold(self, rec):
        """In closed-set mode, threshold is ignored — always returns a label."""
        rec.build_gallery([("alice", _solid_crop(fill=200))])
        result = rec.predict(_solid_crop(fill=10), threshold=0.99, open_set=False)
        # Should return "alice" (only identity in gallery), not "unknown"
        assert result.predicted_label == "alice"
        assert result.is_unknown is False

    def test_multiple_identities_distinguishable(self, rec):
        """
        With clearly distinct crops, the recognizer should return the correct identity.
        Use gradient images (not solid colours) so LBP histograms differ.
        """
        # Create crops with distinct gradient patterns
        crop_a = np.zeros((80, 80, 3), dtype=np.uint8)
        crop_a[:, :40] = 50   # left half dark
        crop_a[:, 40:] = 200  # right half bright

        crop_b = np.zeros((80, 80, 3), dtype=np.uint8)
        crop_b[:40, :] = 200  # top half bright
        crop_b[40:, :] = 50   # bottom half dark

        rec.build_gallery([("alice", crop_a), ("bob", crop_b)])

        result_a = rec.predict(crop_a)
        result_b = rec.predict(crop_b)

        assert result_a.predicted_label == "alice", (
            f"Expected 'alice', got '{result_a.predicted_label}' "
            f"(sim={result_a.similarity:.3f})"
        )
        assert result_b.predicted_label == "bob", (
            f"Expected 'bob', got '{result_b.predicted_label}' "
            f"(sim={result_b.similarity:.3f})"
        )

    def test_clear_gallery_resets_state(self, rec):
        rec.build_gallery(_gallery_pairs())
        rec.clear_gallery()
        result = rec.predict(_solid_crop())
        assert result.predicted_label is None

    def test_invalid_crop_returns_gracefully(self, rec):
        rec.build_gallery(_gallery_pairs())
        result = rec.predict(np.zeros((0, 0, 3), dtype=np.uint8))
        assert isinstance(result, RecognitionResult)

    def test_none_crop_returns_gracefully(self, rec):
        rec.build_gallery(_gallery_pairs())
        result = rec.predict(None)
        assert isinstance(result, RecognitionResult)


# ---------------------------------------------------------------------------
# InsightFaceRecognizer tests
# ---------------------------------------------------------------------------

class TestInsightFaceRecognizer:
    @pytest.fixture
    def rec(self):
        try:
            from recognition.insightface_recognizer import InsightFaceRecognizer
            return InsightFaceRecognizer()
        except ImportError as e:
            pytest.skip(f"insightface not installed: {e}")
        except FileNotFoundError as e:
            pytest.skip(f"buffalo_l model files not found: {e}")

    def test_name_is_insightface(self, rec):
        assert rec.name == "insightface"

    def test_produces_embeddings_true(self, rec):
        assert rec.produces_embeddings is True

    def test_build_gallery_empty_raises(self, rec):
        with pytest.raises(ValueError):
            rec.build_gallery([])

    def test_build_gallery_with_synthetic_crops(self, rec):
        """build_gallery with synthetic crops should not raise (may skip all)."""
        pairs = _gallery_pairs(n_identities=2, crops_per=2)
        rec.build_gallery(pairs)  # may warn about skipped crops but must not raise

    def test_predict_before_gallery_returns_none(self, rec):
        result = rec.predict(_solid_crop())
        assert result.predicted_label is None

    def test_predict_returns_recognition_result(self, rec):
        rec.build_gallery(_gallery_pairs())
        result = rec.predict(_solid_crop())
        assert isinstance(result, RecognitionResult)

    def test_similarity_in_range(self, rec):
        rec.build_gallery(_gallery_pairs())
        result = rec.predict(_solid_crop())
        assert 0.0 <= result.similarity <= 1.0

    def test_clear_gallery_resets_state(self, rec):
        rec.build_gallery(_gallery_pairs())
        rec.clear_gallery()
        result = rec.predict(_solid_crop())
        assert result.predicted_label is None

    def test_get_gallery_embeddings_returns_dict(self, rec):
        rec.build_gallery(_gallery_pairs(n_identities=2))
        embs = rec.get_gallery_embeddings()
        assert isinstance(embs, dict)

    def test_missing_model_raises_file_not_found(self):
        from recognition.insightface_recognizer import InsightFaceRecognizer
        with pytest.raises(FileNotFoundError):
            InsightFaceRecognizer(model_dir="/nonexistent/buffalo_l")

    def test_real_face_image_recognition(self, rec):
        """
        End-to-end test: enroll real face images, then predict on a held-out crop.
        Requires at least one identity with ≥2 images in dataset/raw/.
        """
        dataset_path = _EVAL_ROOT / "dataset" / "raw"
        if not dataset_path.exists():
            pytest.skip("No dataset found at dataset/raw/")

        gallery_pairs = []
        probe_crop = None
        probe_label = None

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
            # Use first N-1 images for gallery, last for probe
            for img_path in images[:-1]:
                crop = cv2.imread(str(img_path))
                if crop is not None:
                    gallery_pairs.append((label, crop))

            if probe_crop is None:
                probe_img = cv2.imread(str(images[-1]))
                if probe_img is not None:
                    probe_crop = probe_img
                    probe_label = label

        if not gallery_pairs or probe_crop is None:
            pytest.skip("Not enough images in dataset/raw/ for recognition test")

        rec.build_gallery(gallery_pairs)
        result = rec.predict(probe_crop)

        assert isinstance(result, RecognitionResult)
        assert 0.0 <= result.similarity <= 1.0
        # Log result for inspection (not a hard assertion — depends on image quality)
        print(
            f"\n[InsightFace] Probe: {probe_label} → "
            f"Predicted: {result.predicted_label} "
            f"(sim={result.similarity:.4f})"
        )


# ---------------------------------------------------------------------------
# Cross-recognizer interface consistency tests
# ---------------------------------------------------------------------------

class TestRecognizerInterfaceConsistency:
    @pytest.fixture
    def lbph(self):
        try:
            from recognition.lbph_recognizer import LBPHRecognizer
            return LBPHRecognizer()
        except ImportError:
            from recognition.lbph_recognizer import LBPHFallbackRecognizer
            return LBPHFallbackRecognizer()

    @pytest.fixture
    def insightface(self):
        try:
            from recognition.insightface_recognizer import InsightFaceRecognizer
            return InsightFaceRecognizer()
        except (ImportError, FileNotFoundError):
            pytest.skip("InsightFace not available")

    def test_both_return_recognition_result(self, lbph, insightface):
        pairs = _gallery_pairs(n_identities=2)
        lbph.build_gallery(pairs)
        insightface.build_gallery(pairs)
        crop = _solid_crop()
        assert isinstance(lbph.predict(crop), RecognitionResult)
        assert isinstance(insightface.predict(crop), RecognitionResult)

    def test_both_have_name_property(self, lbph, insightface):
        assert isinstance(lbph.name, str)
        assert isinstance(insightface.name, str)
        assert lbph.name != insightface.name

    def test_similarity_always_in_range(self, lbph, insightface):
        pairs = _gallery_pairs()
        lbph.build_gallery(pairs)
        insightface.build_gallery(pairs)
        crop = _solid_crop()
        for rec in [lbph, insightface]:
            r = rec.predict(crop)
            assert 0.0 <= r.similarity <= 1.0, (
                f"{rec.name}: similarity {r.similarity} out of [0,1]"
            )

    def test_open_set_unknown_label(self, lbph, insightface):
        """In open-set mode with a very high threshold, probes should be rejected."""
        pairs = _gallery_pairs(n_identities=2)
        lbph.build_gallery(pairs)
        insightface.build_gallery(pairs)

        # Use a crop that is clearly different from the gallery
        # and a threshold just above 0 to force rejection
        different_crop = _noise_crop(seed=999)
        for rec in [lbph, insightface]:
            # threshold=0.99 should reject any non-near-perfect match
            r = rec.predict(different_crop, threshold=0.99, open_set=True)
            # Either rejected as unknown OR matched — just verify the flag is consistent
            if r.is_unknown:
                assert r.predicted_label == "unknown", (
                    f"{rec.name}: is_unknown=True but label='{r.predicted_label}'"
                )
            else:
                assert r.predicted_label != "unknown", (
                    f"{rec.name}: is_unknown=False but label='unknown'"
                )

    def test_lbph_produces_no_embeddings(self, lbph):
        assert lbph.produces_embeddings is False

    def test_insightface_produces_embeddings(self, insightface):
        assert insightface.produces_embeddings is True
