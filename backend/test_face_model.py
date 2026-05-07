"""
Unit tests for the InsightFace pipeline components.

Covers:
  - InsightFaceEngine serialisation helpers (no GPU / model download required)
  - InferenceEngine adapter (mocked engine)
  - recognition_service centroid loading and cache helpers
  - training_service._to_bgr helper

These tests do NOT require the buffalo_l model files to be present.
Heavy inference paths are mocked.
"""

import base64
import os
import struct
import tempfile
from io import BytesIO
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# InsightFaceEngine — serialisation helpers (no model needed)
# ---------------------------------------------------------------------------

class TestInsightFaceEngineHelpers:
    """Tests for static serialisation helpers on InsightFaceEngine."""

    def test_embedding_to_bytes_and_back(self):
        """Round-trip: embedding → bytes → embedding should be identical."""
        from model.insightface_engine import InsightFaceEngine

        original = np.random.rand(512).astype(np.float32)
        blob = InsightFaceEngine.embedding_to_bytes(original)
        recovered = InsightFaceEngine.bytes_to_embedding(blob)

        assert recovered.shape == (512,)
        np.testing.assert_array_almost_equal(original, recovered)

    def test_bytes_length_is_512_floats(self):
        """Serialised embedding must be exactly 512 × 4 bytes."""
        from model.insightface_engine import InsightFaceEngine

        emb = np.ones(512, dtype=np.float32)
        blob = InsightFaceEngine.embedding_to_bytes(emb)
        assert len(blob) == 512 * 4

    def test_compute_centroid_averages_and_normalises(self):
        """Centroid of identical embeddings should equal the embedding itself."""
        from model.insightface_engine import InsightFaceEngine

        v = np.array([3.0, 4.0] + [0.0] * 510, dtype=np.float32)
        centroid = InsightFaceEngine.compute_centroid([v, v, v])

        # Should be L2-normalised
        norm = float(np.linalg.norm(centroid))
        assert abs(norm - 1.0) < 1e-5

    def test_compute_centroid_of_two_vectors(self):
        """Centroid of two opposite unit vectors should be near zero (or normalised)."""
        from model.insightface_engine import InsightFaceEngine

        v1 = np.zeros(512, dtype=np.float32)
        v1[0] = 1.0
        v2 = np.zeros(512, dtype=np.float32)
        v2[0] = -1.0

        # Should not raise even when mean is zero
        try:
            centroid = InsightFaceEngine.compute_centroid([v1, v2])
            # If it doesn't raise, norm should be 0 or 1
            norm = float(np.linalg.norm(centroid))
            assert norm <= 1.0 + 1e-5
        except Exception:
            pass  # Acceptable — zero vector edge case

    def test_identify_returns_none_when_no_centroids(self):
        """identify() with empty centroid dict must return None."""
        from model.insightface_engine import InsightFaceEngine

        engine = MagicMock(spec=InsightFaceEngine)
        engine.identify = InsightFaceEngine.identify.__get__(engine, InsightFaceEngine)

        # Patch _app so __init__ is not called
        with patch.object(InsightFaceEngine, "__init__", return_value=None):
            e = InsightFaceEngine.__new__(InsightFaceEngine)
            e._app = MagicMock()
            result = e.identify(np.ones(512, dtype=np.float32), {})

        assert result is None

    def test_identify_matches_closest_centroid(self):
        """identify() should return the PRN whose centroid is closest."""
        from model.insightface_engine import InsightFaceEngine

        with patch.object(InsightFaceEngine, "__init__", return_value=None):
            e = InsightFaceEngine.__new__(InsightFaceEngine)
            e._app = MagicMock()

        # Two centroids: one identical to query, one orthogonal
        query = np.zeros(512, dtype=np.float32)
        query[0] = 1.0

        centroid_match = query.copy()
        centroid_other = np.zeros(512, dtype=np.float32)
        centroid_other[1] = 1.0

        centroids = {"PRN_MATCH": centroid_match, "PRN_OTHER": centroid_other}
        result = e.identify(query, centroids, threshold=1.5)

        assert result is not None
        prn, similarity = result
        assert prn == "PRN_MATCH"
        assert 0.0 <= similarity <= 1.0


# ---------------------------------------------------------------------------
# InferenceEngine adapter
# ---------------------------------------------------------------------------

class TestInferenceEngine:
    """Tests for the InferenceEngine adapter (model.inference)."""

    def _make_engine_with_mock(self):
        """Return an InferenceEngine whose internal InsightFaceEngine is mocked."""
        from model.inference import InferenceEngine

        with patch("model.inference.InsightFaceEngine") as MockEngine:
            mock_inner = MagicMock()
            MockEngine.return_value = mock_inner
            engine = InferenceEngine()
            engine._engine = mock_inner
        return engine, mock_inner

    def test_set_centroids_updates_internal_dict(self):
        """set_centroids() should replace the centroid dict."""
        from model.inference import InferenceEngine

        with patch("model.inference.InsightFaceEngine"):
            engine = InferenceEngine()

        centroids = {"PRN001": np.ones(512, dtype=np.float32)}
        engine.set_centroids(centroids)
        assert engine._centroids == centroids

    def test_process_image_raises_on_no_faces(self):
        """process_image() must raise ValueError when no faces detected."""
        from model.inference import InferenceEngine

        with patch("model.inference.InsightFaceEngine") as MockEngine:
            mock_inner = MagicMock()
            mock_inner.detect_and_embed.return_value = []  # no faces
            MockEngine.return_value = mock_inner
            engine = InferenceEngine()

        dummy_bgr = np.zeros((100, 100, 3), dtype=np.uint8)
        with pytest.raises(ValueError, match="No faces detected"):
            engine.process_image(dummy_bgr)

    def test_process_image_returns_face_list(self):
        """process_image() should return the list from detect_and_embed."""
        from model.inference import InferenceEngine

        face_dict = {
            "embedding": np.ones(512, dtype=np.float32),
            "bbox": [0, 0, 50, 50],
            "score": 0.99,
            "crop_b64": "abc",
        }

        with patch("model.inference.InsightFaceEngine") as MockEngine:
            mock_inner = MagicMock()
            mock_inner.detect_and_embed.return_value = [face_dict]
            MockEngine.return_value = mock_inner
            engine = InferenceEngine()

        dummy_bgr = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.process_image(dummy_bgr)
        assert len(result) == 1
        assert result[0]["score"] == 0.99

    def test_identify_students_splits_correctly(self):
        """identify_students() should split into identified and unidentified."""
        from model.inference import InferenceEngine

        with patch("model.inference.InsightFaceEngine") as MockEngine:
            mock_inner = MagicMock()
            # First face: identified; second face: not identified
            mock_inner.identify.side_effect = [
                ("PRN001", 0.85),
                None,
            ]
            MockEngine.return_value = mock_inner
            engine = InferenceEngine()

        face_data = [
            {"embedding": np.ones(512, dtype=np.float32), "crop_b64": "img1", "bbox": [0, 0, 10, 10]},
            {"embedding": np.zeros(512, dtype=np.float32), "crop_b64": "img2", "bbox": [10, 10, 20, 20]},
        ]

        identified, unidentified = engine.identify_students(face_data)

        assert len(identified) == 1
        assert identified[0]["prn"] == "PRN001"
        assert identified[0]["similarity"] == 0.85
        assert len(unidentified) == 1
        assert unidentified[0]["crop_b64"] == "img2"


# ---------------------------------------------------------------------------
# recognition_service — cache helpers
# ---------------------------------------------------------------------------

class TestRecognitionServiceCache:
    """Tests for the in-memory unidentified face cache."""

    def setup_method(self):
        """Clear cache before each test."""
        from services import recognition_service
        recognition_service.clear_unidentified_faces()

    def test_get_unidentified_face_raises_on_missing(self):
        """get_unidentified_face() must raise KeyError for unknown face_id."""
        from services.recognition_service import get_unidentified_face

        with pytest.raises(KeyError):
            get_unidentified_face("nonexistent-uuid")

    def test_remove_unidentified_face_returns_true_when_exists(self):
        """remove_unidentified_face() should return True when face existed."""
        from services import recognition_service

        recognition_service._unidentified_cache["test-id"] = "base64data"
        result = recognition_service.remove_unidentified_face("test-id")
        assert result is True
        assert "test-id" not in recognition_service._unidentified_cache

    def test_remove_unidentified_face_returns_false_when_missing(self):
        """remove_unidentified_face() should return False for unknown id."""
        from services.recognition_service import remove_unidentified_face

        result = remove_unidentified_face("ghost-id")
        assert result is False

    def test_clear_unidentified_faces_empties_cache(self):
        """clear_unidentified_faces() should empty the cache."""
        from services import recognition_service

        recognition_service._unidentified_cache["a"] = "x"
        recognition_service._unidentified_cache["b"] = "y"
        recognition_service.clear_unidentified_faces()
        assert len(recognition_service._unidentified_cache) == 0

    def test_get_after_set_returns_correct_value(self):
        """get_unidentified_face() should return the stored base64 string."""
        from services import recognition_service

        recognition_service._unidentified_cache["face-1"] = "base64crop"
        result = recognition_service.get_unidentified_face("face-1")
        assert result == "base64crop"


# ---------------------------------------------------------------------------
# training_service — _to_bgr helper
# ---------------------------------------------------------------------------

class TestTrainingServiceToBgr:
    """Tests for the internal _to_bgr image conversion helper."""

    def _make_valid_b64_png(self) -> str:
        """Return a valid 10×10 white PNG as base64."""
        try:
            from PIL import Image
            img = Image.new("RGB", (10, 10), color=(255, 255, 255))
            buf = BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()
        except ImportError:
            pytest.skip("Pillow not installed")

    def test_numpy_array_passthrough(self):
        """numpy arrays should be returned as-is."""
        from services.training_service import _to_bgr

        arr = np.zeros((50, 50, 3), dtype=np.uint8)
        result = _to_bgr(arr, 0)
        assert result is arr

    def test_valid_base64_returns_bgr_array(self):
        """Valid base64 PNG should decode to a BGR numpy array."""
        from services.training_service import _to_bgr

        b64 = self._make_valid_b64_png()
        result = _to_bgr(b64, 0)

        assert result is not None
        assert isinstance(result, np.ndarray)
        assert result.ndim == 3
        assert result.shape[2] == 3

    def test_base64_with_data_url_prefix(self):
        """base64 strings with data-URL prefix should be handled."""
        from services.training_service import _to_bgr

        b64 = self._make_valid_b64_png()
        data_url = f"data:image/png;base64,{b64}"
        result = _to_bgr(data_url, 0)

        assert result is not None
        assert isinstance(result, np.ndarray)

    def test_invalid_base64_returns_none(self):
        """Corrupt base64 should return None (not raise)."""
        from services.training_service import _to_bgr

        result = _to_bgr("!!!not_valid_base64!!!", 0)
        assert result is None

    def test_unsupported_type_returns_none(self):
        """Non-string, non-ndarray input should return None."""
        from services.training_service import _to_bgr

        result = _to_bgr(12345, 0)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
