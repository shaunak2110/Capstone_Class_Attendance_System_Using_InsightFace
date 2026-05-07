"""
Tests for ExperimentConfig — covers:
  - Loading from a valid YAML file
  - Loading from a dict with all required keys
  - Default value application
  - Missing required key raises ValueError naming the key
  - Invalid value ranges raise ValueError
  - Property 18: Config missing-key detection (hypothesis-based)

Run from workspace root:
    python -m pytest backend/evaluation/tests/test_config.py -v
"""

import sys
import os
from pathlib import Path

# Ensure backend/evaluation is on sys.path so imports work without installation
_EVAL_ROOT = Path(__file__).resolve().parent.parent
if str(_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_EVAL_ROOT))

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from configs.config import ExperimentConfig, _REQUIRED_KEYS, _DEFAULTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_dict() -> dict:
    """Smallest valid config dict — only required keys."""
    return {
        "dataset_path": "dataset/raw",
        "detectors": ["haarcascade"],
        "recognizers": ["lbph"],
    }


def _full_dict() -> dict:
    """Full config dict with all keys explicitly set."""
    return {
        "dataset_path": "dataset/raw",
        "gallery_ratio": 0.70,
        "random_seed": 42,
        "image_size": [640, 640],
        "detectors": ["insightface", "haarcascade", "retinaface"],
        "recognizers": ["insightface", "lbph", "dlib"],
        "similarity_threshold": 0.85,
        "output_dir": "results/",
        "open_set_ratio": 0.0,
        "num_runs": 1,
    }


# ---------------------------------------------------------------------------
# Basic construction tests
# ---------------------------------------------------------------------------

class TestFromDict:
    def test_minimal_dict_succeeds(self):
        cfg = ExperimentConfig.from_dict(_minimal_dict())
        assert cfg.dataset_path == Path("dataset/raw")
        assert cfg.detectors == ["haarcascade"]
        assert cfg.recognizers == ["lbph"]

    def test_defaults_applied(self):
        cfg = ExperimentConfig.from_dict(_minimal_dict())
        assert cfg.gallery_ratio == 0.70
        assert cfg.random_seed == 42
        assert cfg.image_size == (640, 640)
        assert cfg.similarity_threshold == 0.85
        assert cfg.output_dir == Path("results/")
        assert cfg.open_set_ratio == 0.0
        assert cfg.num_runs == 1

    def test_full_dict_succeeds(self):
        cfg = ExperimentConfig.from_dict(_full_dict())
        assert cfg.gallery_ratio == 0.70
        assert cfg.random_seed == 42
        assert cfg.image_size == (640, 640)
        assert cfg.detectors == ["insightface", "haarcascade", "retinaface"]
        assert cfg.recognizers == ["insightface", "lbph", "dlib"]
        assert cfg.similarity_threshold == 0.85
        assert cfg.output_dir == Path("results/")
        assert cfg.open_set_ratio == 0.0
        assert cfg.num_runs == 1

    def test_custom_values_override_defaults(self):
        d = _minimal_dict()
        d["gallery_ratio"] = 0.80
        d["random_seed"] = 99
        d["num_runs"] = 5
        d["open_set_ratio"] = 0.2
        cfg = ExperimentConfig.from_dict(d)
        assert cfg.gallery_ratio == 0.80
        assert cfg.random_seed == 99
        assert cfg.num_runs == 5
        assert cfg.open_set_ratio == 0.2

    def test_dataset_path_is_path_object(self):
        cfg = ExperimentConfig.from_dict(_minimal_dict())
        assert isinstance(cfg.dataset_path, Path)

    def test_output_dir_is_path_object(self):
        cfg = ExperimentConfig.from_dict(_minimal_dict())
        assert isinstance(cfg.output_dir, Path)

    def test_image_size_is_tuple(self):
        cfg = ExperimentConfig.from_dict(_minimal_dict())
        assert isinstance(cfg.image_size, tuple)
        assert len(cfg.image_size) == 2


# ---------------------------------------------------------------------------
# Missing required key tests
# ---------------------------------------------------------------------------

class TestMissingRequiredKeys:
    def test_missing_dataset_path_raises(self):
        d = _minimal_dict()
        del d["dataset_path"]
        with pytest.raises(ValueError, match="dataset_path"):
            ExperimentConfig.from_dict(d)

    def test_missing_detectors_raises(self):
        d = _minimal_dict()
        del d["detectors"]
        with pytest.raises(ValueError, match="detectors"):
            ExperimentConfig.from_dict(d)

    def test_missing_recognizers_raises(self):
        d = _minimal_dict()
        del d["recognizers"]
        with pytest.raises(ValueError, match="recognizers"):
            ExperimentConfig.from_dict(d)

    def test_empty_dict_raises_with_key_name(self):
        with pytest.raises(ValueError) as exc_info:
            ExperimentConfig.from_dict({})
        # Error message must name a missing key
        error_msg = str(exc_info.value)
        assert any(key in error_msg for key in _REQUIRED_KEYS)

    def test_error_message_names_missing_key(self):
        """The ValueError message must contain the name of the missing key."""
        d = _minimal_dict()
        del d["dataset_path"]
        with pytest.raises(ValueError) as exc_info:
            ExperimentConfig.from_dict(d)
        assert "dataset_path" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestValidation:
    def test_gallery_ratio_zero_raises(self):
        d = _minimal_dict()
        d["gallery_ratio"] = 0.0
        with pytest.raises(ValueError, match="gallery_ratio"):
            ExperimentConfig.from_dict(d)

    def test_gallery_ratio_one_raises(self):
        d = _minimal_dict()
        d["gallery_ratio"] = 1.0
        with pytest.raises(ValueError, match="gallery_ratio"):
            ExperimentConfig.from_dict(d)

    def test_gallery_ratio_negative_raises(self):
        d = _minimal_dict()
        d["gallery_ratio"] = -0.1
        with pytest.raises(ValueError, match="gallery_ratio"):
            ExperimentConfig.from_dict(d)

    def test_open_set_ratio_one_raises(self):
        d = _minimal_dict()
        d["open_set_ratio"] = 1.0
        with pytest.raises(ValueError, match="open_set_ratio"):
            ExperimentConfig.from_dict(d)

    def test_open_set_ratio_negative_raises(self):
        d = _minimal_dict()
        d["open_set_ratio"] = -0.1
        with pytest.raises(ValueError, match="open_set_ratio"):
            ExperimentConfig.from_dict(d)

    def test_open_set_ratio_zero_is_valid(self):
        d = _minimal_dict()
        d["open_set_ratio"] = 0.0
        cfg = ExperimentConfig.from_dict(d)
        assert cfg.open_set_ratio == 0.0

    def test_num_runs_zero_raises(self):
        d = _minimal_dict()
        d["num_runs"] = 0
        with pytest.raises(ValueError, match="num_runs"):
            ExperimentConfig.from_dict(d)

    def test_num_runs_negative_raises(self):
        d = _minimal_dict()
        d["num_runs"] = -1
        with pytest.raises(ValueError, match="num_runs"):
            ExperimentConfig.from_dict(d)

    def test_image_size_wrong_length_raises(self):
        d = _minimal_dict()
        d["image_size"] = [640]
        with pytest.raises(ValueError, match="image_size"):
            ExperimentConfig.from_dict(d)

    def test_empty_detectors_raises(self):
        d = _minimal_dict()
        d["detectors"] = []
        with pytest.raises(ValueError, match="detectors"):
            ExperimentConfig.from_dict(d)

    def test_empty_recognizers_raises(self):
        d = _minimal_dict()
        d["recognizers"] = []
        with pytest.raises(ValueError, match="recognizers"):
            ExperimentConfig.from_dict(d)


# ---------------------------------------------------------------------------
# YAML file loading tests
# ---------------------------------------------------------------------------

class TestFromYaml:
    def test_loads_default_config_file(self):
        """The bundled experiment_config.yaml must load without errors."""
        config_path = _EVAL_ROOT / "configs" / "experiment_config.yaml"
        cfg = ExperimentConfig.from_yaml(config_path)
        assert cfg.gallery_ratio == 0.70
        assert cfg.random_seed == 42
        assert "insightface" in cfg.detectors
        assert "lbph" in cfg.recognizers

    def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            ExperimentConfig.from_yaml("nonexistent_config.yaml")

    def test_roundtrip_yaml(self, tmp_path):
        """Write a YAML file and load it back — values must match."""
        data = _full_dict()
        yaml_file = tmp_path / "test_config.yaml"
        with yaml_file.open("w") as fh:
            yaml.dump(data, fh)
        cfg = ExperimentConfig.from_yaml(yaml_file)
        assert cfg.gallery_ratio == data["gallery_ratio"]
        assert cfg.random_seed == data["random_seed"]
        assert cfg.detectors == data["detectors"]
        assert cfg.recognizers == data["recognizers"]

    def test_empty_yaml_raises_value_error(self, tmp_path):
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        with pytest.raises(ValueError, match="empty"):
            ExperimentConfig.from_yaml(yaml_file)


# ---------------------------------------------------------------------------
# Property 18: Config missing-key detection (hypothesis-based)
# ---------------------------------------------------------------------------

# All required keys
_ALL_REQUIRED = list(_REQUIRED_KEYS)


@given(
    missing_keys=st.lists(
        st.sampled_from(_ALL_REQUIRED),
        min_size=1,
        max_size=len(_ALL_REQUIRED),
        unique=True,
    )
)
@settings(max_examples=50)
def test_property_18_missing_key_raises_value_error_with_key_name(missing_keys):
    """
    Property 18: Config missing-key detection.

    For any config dict missing one or more required keys, from_dict() raises
    ValueError and the error message contains the name of a missing key.

    Validates: Requirement 10.3
    """
    d = _full_dict()
    for key in missing_keys:
        del d[key]

    with pytest.raises(ValueError) as exc_info:
        ExperimentConfig.from_dict(d)

    error_msg = str(exc_info.value)
    # At least one of the missing keys must appear in the error message
    assert any(key in error_msg for key in missing_keys), (
        f"ValueError message '{error_msg}' does not name any of the "
        f"missing keys: {missing_keys}"
    )


# ---------------------------------------------------------------------------
# resolve_output_dirs test
# ---------------------------------------------------------------------------

class TestResolveOutputDirs:
    def test_creates_output_subdirectories(self, tmp_path):
        d = _minimal_dict()
        d["output_dir"] = str(tmp_path / "results")
        cfg = ExperimentConfig.from_dict(d)
        cfg.resolve_output_dirs()
        assert (tmp_path / "results" / "logs" / "failures").is_dir()
        assert (tmp_path / "results" / "plots").is_dir()
        assert (tmp_path / "results" / "reports").is_dir()

    def test_idempotent_when_dirs_exist(self, tmp_path):
        d = _minimal_dict()
        d["output_dir"] = str(tmp_path / "results")
        cfg = ExperimentConfig.from_dict(d)
        cfg.resolve_output_dirs()
        cfg.resolve_output_dirs()  # second call must not raise
