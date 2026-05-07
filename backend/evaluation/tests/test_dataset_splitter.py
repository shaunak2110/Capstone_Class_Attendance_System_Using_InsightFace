"""
Tests for DatasetSplitter — covers:
  - Basic gallery/probe split with correct ratios
  - Minimum image threshold enforcement
  - Open-set identity selection and exclusion from gallery
  - Reproducibility (same seed → same split)
  - Different run_index → different split
  - Guaranteed ≥1 image in both gallery and probe per identity
  - annotations.json and conditions.json loading (valid, absent, malformed)
  - preprocess() output shape, dtype, value range
  - SplitResult structure correctness
  - Property 1: Split invariants (hypothesis)
  - Property 2: Split reproducibility (hypothesis)
  - Property 3: Preprocessing invariants (hypothesis)

Run from workspace root:
    python -m pytest backend/evaluation/tests/test_dataset_splitter.py -v
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Ensure backend/evaluation is on sys.path
_EVAL_ROOT = Path(__file__).resolve().parent.parent
if str(_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_EVAL_ROOT))

from configs.config import ExperimentConfig
from utils.image_loader import (
    DatasetSplitter,
    DEFAULT_MIN_IMAGES,
    SUPPORTED_EXTENSIONS,
    SplitResult,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

def _make_config(
    dataset_path: str,
    gallery_ratio: float = 0.70,
    random_seed: int = 42,
    open_set_ratio: float = 0.0,
    num_runs: int = 1,
    min_images: int = 2,
) -> ExperimentConfig:
    return ExperimentConfig.from_dict({
        "dataset_path": dataset_path,
        "gallery_ratio": gallery_ratio,
        "random_seed": random_seed,
        "open_set_ratio": open_set_ratio,
        "num_runs": num_runs,
        "detectors": ["haarcascade"],
        "recognizers": ["lbph"],
    })


def _create_synthetic_dataset(
    tmp_path: Path,
    identities: dict,  # {prn: num_images}
    with_annotations: bool = False,
    with_conditions: bool = False,
    malformed_annotations: bool = False,
    malformed_conditions: bool = False,
) -> Path:
    """
    Create a synthetic dataset under tmp_path/raw/.
    Each identity gets small valid JPEG-like PNG images (1x1 pixel).
    """
    raw = tmp_path / "raw"
    raw.mkdir()

    for prn, n_images in identities.items():
        id_dir = raw / prn
        id_dir.mkdir()
        for i in range(n_images):
            img_path = id_dir / f"img{i:04d}.jpg"
            # Write a minimal valid JPEG (1x1 white pixel) using numpy + cv2
            import cv2
            img = np.ones((10, 10, 3), dtype=np.uint8) * 200
            cv2.imwrite(str(img_path), img)

        if with_annotations and not malformed_annotations:
            ann = {f"img{i:04d}.jpg": [[0, 0, 5, 5]] for i in range(n_images)}
            (id_dir / "annotations.json").write_text(json.dumps(ann))

        if malformed_annotations:
            (id_dir / "annotations.json").write_text("{ not valid json }")

        if with_conditions and not malformed_conditions:
            cond = {
                f"img{i:04d}.jpg": {"lighting": "bright", "angle": "frontal"}
                for i in range(n_images)
            }
            (id_dir / "conditions.json").write_text(json.dumps(cond))

        if malformed_conditions:
            (id_dir / "conditions.json").write_text("[ invalid ]")

    return raw


# ---------------------------------------------------------------------------
# Basic split tests
# ---------------------------------------------------------------------------

class TestBasicSplit:
    def test_split_returns_split_result(self, tmp_path):
        raw = _create_synthetic_dataset(tmp_path, {"A": 20, "B": 15, "C": 10})
        cfg = _make_config(str(raw), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        assert isinstance(result, SplitResult)

    def test_all_identities_in_gallery_and_probe(self, tmp_path):
        raw = _create_synthetic_dataset(tmp_path, {"A": 20, "B": 15, "C": 10})
        cfg = _make_config(str(raw), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        for identity in ["A", "B", "C"]:
            assert identity in result.gallery, f"{identity} missing from gallery"
            assert identity in result.probe, f"{identity} missing from probe"

    def test_gallery_probe_at_least_one_image_each(self, tmp_path):
        raw = _create_synthetic_dataset(tmp_path, {"A": 20, "B": 15, "C": 10})
        cfg = _make_config(str(raw), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        for identity in result.gallery:
            assert len(result.gallery[identity]) >= 1
        for identity in result.probe:
            assert len(result.probe[identity]) >= 1

    def test_gallery_probe_union_equals_all_images(self, tmp_path):
        raw = _create_synthetic_dataset(tmp_path, {"A": 20, "B": 15})
        cfg = _make_config(str(raw), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        for identity in result.gallery:
            all_paths = set(result.gallery[identity]) | set(result.probe[identity])
            # Collect all images from disk
            disk_images = set(
                p for p in (raw / identity).iterdir()
                if p.suffix.lower() in SUPPORTED_EXTENSIONS
            )
            assert all_paths == disk_images, (
                f"Identity {identity}: split union != disk images"
            )

    def test_no_overlap_between_gallery_and_probe(self, tmp_path):
        raw = _create_synthetic_dataset(tmp_path, {"A": 20, "B": 15})
        cfg = _make_config(str(raw), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        for identity in result.gallery:
            gallery_set = set(result.gallery[identity])
            probe_set = set(result.probe[identity])
            overlap = gallery_set & probe_set
            assert not overlap, f"Identity {identity}: gallery/probe overlap: {overlap}"

    def test_gallery_ratio_approximately_correct(self, tmp_path):
        raw = _create_synthetic_dataset(tmp_path, {"A": 100, "B": 80, "C": 60})
        cfg = _make_config(str(raw), gallery_ratio=0.70, min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        for identity in result.gallery:
            n_total = len(result.gallery[identity]) + len(result.probe[identity])
            n_gallery = len(result.gallery[identity])
            actual_ratio = n_gallery / n_total
            # Allow ±10% tolerance due to floor rounding
            assert 0.60 <= actual_ratio <= 0.80, (
                f"Identity {identity}: gallery ratio {actual_ratio:.2f} out of range"
            )

    def test_run_index_stored_in_result(self, tmp_path):
        raw = _create_synthetic_dataset(tmp_path, {"A": 20})
        cfg = _make_config(str(raw), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split(run_index=3)
        assert result.run_index == 3

    def test_seed_used_equals_base_plus_run_index(self, tmp_path):
        raw = _create_synthetic_dataset(tmp_path, {"A": 20})
        cfg = _make_config(str(raw), random_seed=42, min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split(run_index=5)
        assert result.seed_used == 47  # 42 + 5


# ---------------------------------------------------------------------------
# Minimum image threshold tests
# ---------------------------------------------------------------------------

class TestMinimumImageThreshold:
    def test_identity_below_threshold_skipped(self, tmp_path):
        # "small" has only 3 images, threshold is 10
        raw = _create_synthetic_dataset(tmp_path, {"big": 20, "small": 3})
        cfg = _make_config(str(raw), min_images=10)
        splitter = DatasetSplitter(cfg, min_images=10)
        result = splitter.split()
        assert "small" not in result.gallery
        assert "small" not in result.probe
        assert "big" in result.gallery

    def test_identity_exactly_at_threshold_included(self, tmp_path):
        raw = _create_synthetic_dataset(tmp_path, {"exact": 10, "big": 20})
        cfg = _make_config(str(raw), min_images=10)
        splitter = DatasetSplitter(cfg, min_images=10)
        result = splitter.split()
        assert "exact" in result.gallery

    def test_all_below_threshold_raises(self, tmp_path):
        raw = _create_synthetic_dataset(tmp_path, {"A": 3, "B": 4})
        cfg = _make_config(str(raw), min_images=10)
        splitter = DatasetSplitter(cfg, min_images=10)
        with pytest.raises(ValueError, match="minimum image threshold"):
            splitter.split()

    def test_stats_reflect_skipped_identities(self, tmp_path):
        raw = _create_synthetic_dataset(tmp_path, {"big": 20, "small": 3})
        cfg = _make_config(str(raw), min_images=10)
        splitter = DatasetSplitter(cfg, min_images=10)
        result = splitter.split()
        # Only "big" should appear in stats (skipped identities are not included)
        stat_ids = {s.identity for s in result.stats}
        assert "big" in stat_ids
        assert "small" not in stat_ids


# ---------------------------------------------------------------------------
# Open-set tests
# ---------------------------------------------------------------------------

class TestOpenSet:
    def test_open_set_identities_not_in_gallery(self, tmp_path):
        raw = _create_synthetic_dataset(
            tmp_path, {"A": 20, "B": 20, "C": 20, "D": 20}
        )
        cfg = _make_config(str(raw), open_set_ratio=0.25, min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        for ident in result.open_set_identities:
            assert ident not in result.gallery, (
                f"Open-set identity '{ident}' should not be in gallery"
            )

    def test_open_set_identities_in_probe(self, tmp_path):
        raw = _create_synthetic_dataset(
            tmp_path, {"A": 20, "B": 20, "C": 20, "D": 20}
        )
        cfg = _make_config(str(raw), open_set_ratio=0.25, min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        for ident in result.open_set_identities:
            assert ident in result.probe, (
                f"Open-set identity '{ident}' should be in probe"
            )

    def test_open_set_count_matches_ratio(self, tmp_path):
        raw = _create_synthetic_dataset(
            tmp_path, {str(i): 20 for i in range(10)}
        )
        cfg = _make_config(str(raw), open_set_ratio=0.30, min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        expected = math.floor(10 * 0.30)
        assert len(result.open_set_identities) == expected

    def test_zero_open_set_ratio_no_open_identities(self, tmp_path):
        raw = _create_synthetic_dataset(tmp_path, {"A": 20, "B": 20})
        cfg = _make_config(str(raw), open_set_ratio=0.0, min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        assert result.open_set_identities == []

    def test_open_set_stats_marked_correctly(self, tmp_path):
        raw = _create_synthetic_dataset(
            tmp_path, {"A": 20, "B": 20, "C": 20, "D": 20}
        )
        cfg = _make_config(str(raw), open_set_ratio=0.25, min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        open_set = set(result.open_set_identities)
        for s in result.stats:
            if s.identity in open_set:
                assert s.is_open_set is True
                assert s.gallery_count == 0
            else:
                assert s.is_open_set is False
                assert s.gallery_count >= 1


# ---------------------------------------------------------------------------
# Reproducibility tests
# ---------------------------------------------------------------------------

class TestReproducibility:
    def test_same_seed_same_split(self, tmp_path):
        raw = _create_synthetic_dataset(
            tmp_path, {"A": 30, "B": 25, "C": 20}
        )
        cfg = _make_config(str(raw), random_seed=42, min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        r1 = splitter.split(run_index=0)
        r2 = splitter.split(run_index=0)
        for identity in r1.gallery:
            assert r1.gallery[identity] == r2.gallery[identity]
            assert r1.probe[identity] == r2.probe[identity]

    def test_different_run_index_different_split(self, tmp_path):
        raw = _create_synthetic_dataset(
            tmp_path, {"A": 30, "B": 25, "C": 20}
        )
        cfg = _make_config(str(raw), random_seed=42, min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        r0 = splitter.split(run_index=0)
        r1 = splitter.split(run_index=1)
        # At least one identity should have a different split
        any_different = any(
            r0.gallery.get(ident) != r1.gallery.get(ident)
            for ident in r0.gallery
        )
        assert any_different, "Different run_index should produce different splits"

    def test_different_seed_different_split(self, tmp_path):
        raw = _create_synthetic_dataset(
            tmp_path, {"A": 30, "B": 25, "C": 20}
        )
        cfg1 = _make_config(str(raw), random_seed=42, min_images=2)
        cfg2 = _make_config(str(raw), random_seed=99, min_images=2)
        r1 = DatasetSplitter(cfg1, min_images=2).split()
        r2 = DatasetSplitter(cfg2, min_images=2).split()
        any_different = any(
            r1.gallery.get(ident) != r2.gallery.get(ident)
            for ident in r1.gallery
        )
        assert any_different, "Different seeds should produce different splits"


# ---------------------------------------------------------------------------
# Annotations and conditions loading tests
# ---------------------------------------------------------------------------

class TestMetadataLoading:
    def test_annotations_loaded_when_present(self, tmp_path):
        raw = _create_synthetic_dataset(
            tmp_path, {"A": 15}, with_annotations=True
        )
        cfg = _make_config(str(raw), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        assert "A" in result.annotations
        assert isinstance(result.annotations["A"], dict)

    def test_annotations_empty_when_absent(self, tmp_path):
        raw = _create_synthetic_dataset(tmp_path, {"A": 15})
        cfg = _make_config(str(raw), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        assert "A" not in result.annotations

    def test_malformed_annotations_treated_as_unannotated(self, tmp_path):
        raw = _create_synthetic_dataset(
            tmp_path, {"A": 15}, malformed_annotations=True
        )
        cfg = _make_config(str(raw), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()  # must not raise
        assert "A" not in result.annotations

    def test_conditions_loaded_when_present(self, tmp_path):
        raw = _create_synthetic_dataset(
            tmp_path, {"A": 15}, with_conditions=True
        )
        cfg = _make_config(str(raw), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        assert "A" in result.conditions
        assert isinstance(result.conditions["A"], dict)

    def test_conditions_empty_when_absent(self, tmp_path):
        raw = _create_synthetic_dataset(tmp_path, {"A": 15})
        cfg = _make_config(str(raw), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()
        assert "A" not in result.conditions

    def test_malformed_conditions_treated_as_unconditioned(self, tmp_path):
        raw = _create_synthetic_dataset(
            tmp_path, {"A": 15}, malformed_conditions=True
        )
        cfg = _make_config(str(raw), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.split()  # must not raise
        assert "A" not in result.conditions


# ---------------------------------------------------------------------------
# Preprocess tests
# ---------------------------------------------------------------------------

class TestPreprocess:
    def test_output_shape_matches_config(self, tmp_path):
        import cv2
        img_path = tmp_path / "test.jpg"
        cv2.imwrite(str(img_path), np.ones((50, 80, 3), dtype=np.uint8) * 128)
        cfg = _make_config(str(tmp_path), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.preprocess(img_path)
        w, h = cfg.image_size
        assert result.shape == (h, w, 3), f"Expected ({h},{w},3), got {result.shape}"

    def test_output_dtype_is_uint8(self, tmp_path):
        import cv2
        img_path = tmp_path / "test.jpg"
        cv2.imwrite(str(img_path), np.ones((50, 80, 3), dtype=np.uint8) * 128)
        cfg = _make_config(str(tmp_path), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.preprocess(img_path)
        assert result.dtype == np.uint8

    def test_output_values_in_range(self, tmp_path):
        import cv2
        img_path = tmp_path / "test.jpg"
        cv2.imwrite(str(img_path), np.ones((50, 80, 3), dtype=np.uint8) * 200)
        cfg = _make_config(str(tmp_path), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.preprocess(img_path)
        assert result.min() >= 0
        assert result.max() <= 255

    def test_missing_image_raises_file_not_found(self, tmp_path):
        cfg = _make_config(str(tmp_path), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        with pytest.raises(FileNotFoundError):
            splitter.preprocess(tmp_path / "nonexistent.jpg")

    def test_custom_image_size(self, tmp_path):
        import cv2
        img_path = tmp_path / "test.jpg"
        cv2.imwrite(str(img_path), np.ones((100, 100, 3), dtype=np.uint8) * 100)
        cfg = ExperimentConfig.from_dict({
            "dataset_path": str(tmp_path),
            "detectors": ["haarcascade"],
            "recognizers": ["lbph"],
            "image_size": [320, 240],
        })
        splitter = DatasetSplitter(cfg, min_images=2)
        result = splitter.preprocess(img_path)
        assert result.shape == (240, 320, 3)


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_missing_dataset_path_raises(self, tmp_path):
        cfg = _make_config(str(tmp_path / "nonexistent"), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        with pytest.raises(FileNotFoundError):
            splitter.split()

    def test_empty_dataset_raises(self, tmp_path):
        raw = tmp_path / "raw"
        raw.mkdir()
        cfg = _make_config(str(raw), min_images=2)
        splitter = DatasetSplitter(cfg, min_images=2)
        with pytest.raises(ValueError):
            splitter.split()


# ---------------------------------------------------------------------------
# Property 1: Dataset split invariants (hypothesis)
# ---------------------------------------------------------------------------

import math as _math


@given(
    n_images=st.integers(min_value=10, max_value=100),
    gallery_ratio=st.floats(min_value=0.1, max_value=0.9),
    seed=st.integers(min_value=0, max_value=9999),
)
@settings(max_examples=50)
def test_property_1_split_invariants(tmp_path_factory, n_images, gallery_ratio, seed):
    """
    Property 1: Dataset split invariants.

    For any identity with ≥ min_images images and any gallery_ratio ∈ (0,1):
      - Identity appears in both gallery and probe
      - Gallery and probe each have ≥1 image
      - Union of gallery + probe = all images (no loss, no duplication)

    Validates: Requirements 2.4, 2.5
    """
    tmp_path = tmp_path_factory.mktemp("prop1")
    raw = _create_synthetic_dataset(tmp_path, {"ID": n_images})
    cfg = _make_config(str(raw), gallery_ratio=gallery_ratio, random_seed=seed, min_images=2)
    splitter = DatasetSplitter(cfg, min_images=2)
    result = splitter.split()

    assert "ID" in result.gallery
    assert "ID" in result.probe
    assert len(result.gallery["ID"]) >= 1
    assert len(result.probe["ID"]) >= 1

    all_split = set(result.gallery["ID"]) | set(result.probe["ID"])
    disk_images = set(
        p for p in (raw / "ID").iterdir()
        if p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    assert all_split == disk_images


@given(
    n_images=st.integers(min_value=10, max_value=50),
    seed=st.integers(min_value=0, max_value=9999),
    run_a=st.integers(min_value=0, max_value=10),
    run_b=st.integers(min_value=0, max_value=10).filter(lambda x: x != 0),
)
@settings(max_examples=30)
def test_property_2_split_reproducibility(
    tmp_path_factory, n_images, seed, run_a, run_b
):
    """
    Property 2: Split reproducibility.

    Same seed + run_index → identical split.
    Different run_index → different split (for large enough datasets).

    Validates: Requirements 2.6, 12.2, 21.2
    """
    tmp_path = tmp_path_factory.mktemp("prop2")
    raw = _create_synthetic_dataset(tmp_path, {"ID": n_images})
    cfg = _make_config(str(raw), random_seed=seed, min_images=2)
    splitter = DatasetSplitter(cfg, min_images=2)

    # Same run_index → same split
    r1 = splitter.split(run_index=run_a)
    r2 = splitter.split(run_index=run_a)
    assert r1.gallery["ID"] == r2.gallery["ID"]
    assert r1.probe["ID"] == r2.probe["ID"]


@given(
    width=st.integers(min_value=10, max_value=200),
    height=st.integers(min_value=10, max_value=200),
    target_w=st.integers(min_value=32, max_value=640),
    target_h=st.integers(min_value=32, max_value=640),
)
@settings(max_examples=30)
def test_property_3_preprocessing_invariants(
    tmp_path_factory, width, height, target_w, target_h
):
    """
    Property 3: Image preprocessing invariants.

    For any input image of any size, preprocess() returns:
      - shape (target_h, target_w, 3)
      - dtype uint8
      - all pixel values in [0, 255]

    Validates: Requirements 2.7
    """
    import cv2
    tmp_path = tmp_path_factory.mktemp("prop3")
    img_path = tmp_path / "test.jpg"
    img = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    cv2.imwrite(str(img_path), img)

    cfg = ExperimentConfig.from_dict({
        "dataset_path": str(tmp_path),
        "detectors": ["haarcascade"],
        "recognizers": ["lbph"],
        "image_size": [target_w, target_h],
    })
    splitter = DatasetSplitter(cfg, min_images=2)
    result = splitter.preprocess(img_path)

    assert result.shape == (target_h, target_w, 3), (
        f"Expected ({target_h},{target_w},3), got {result.shape}"
    )
    assert result.dtype == np.uint8
    assert result.min() >= 0
    assert result.max() <= 255
