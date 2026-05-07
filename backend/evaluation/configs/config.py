"""
ExperimentConfig — single source of truth for all evaluation pipeline parameters.

Loaded from configs/experiment_config.yaml via ExperimentConfig.from_yaml().
All paths are resolved relative to the backend/evaluation/ directory.

Usage:
    from configs.config import ExperimentConfig
    cfg = ExperimentConfig.from_yaml("configs/experiment_config.yaml")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

import yaml


# ---------------------------------------------------------------------------
# Required keys — any of these missing in the YAML raises ValueError
# ---------------------------------------------------------------------------
_REQUIRED_KEYS = {"dataset_path", "detectors", "recognizers"}

# ---------------------------------------------------------------------------
# Defaults for optional keys
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "gallery_ratio": 0.70,
    "random_seed": 42,
    "image_size": [640, 640],
    "similarity_threshold": 0.85,
    "output_dir": "results/",
    "open_set_ratio": 0.0,
    "num_runs": 1,
}


@dataclass
class ExperimentConfig:
    """
    All tunable parameters for one evaluation run.

    Attributes:
        dataset_path:         Path to the raw dataset directory (contains per-identity
                              sub-folders).
        gallery_ratio:        Fraction of images per identity used for the gallery
                              (training split). Must be in (0, 1). Default 0.70.
        random_seed:          Integer seed for reproducible shuffling. Default 42.
        image_size:           (width, height) tuple for preprocessing resize.
                              Default (640, 640).
        detectors:            List of detector names to enable.
                              Valid values: "insightface", "haarcascade",
                              "retinaface", "yolo".
        recognizers:          List of recognizer names to enable.
                              Valid values: "insightface", "lbph", "dlib".
        similarity_threshold: Match/no-match decision boundary for embedding-based
                              recognizers. Default 0.85.
        output_dir:           Root directory for all results output. Default "results/".
        open_set_ratio:       Fraction of identities withheld from the gallery entirely
                              (open-set evaluation). 0.0 = closed-set. Default 0.0.
        num_runs:             Number of times each experiment is repeated with a
                              different random split. Default 1.
    """

    dataset_path: Path
    detectors: List[str]
    recognizers: List[str]

    gallery_ratio: float = 0.70
    random_seed: int = 42
    image_size: Tuple[int, int] = (640, 640)
    similarity_threshold: float = 0.85
    output_dir: Path = field(default_factory=lambda: Path("results/"))
    open_set_ratio: float = 0.0
    num_runs: int = 1

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, d: dict) -> "ExperimentConfig":
        """
        Build an ExperimentConfig from a plain dictionary (e.g. parsed YAML).

        Raises:
            ValueError: If any required key is missing from ``d``.  The error
                        message names the first missing key found.
        """
        # Validate required keys
        for key in _REQUIRED_KEYS:
            if key not in d:
                raise ValueError(
                    f"Missing required configuration key: '{key}'. "
                    f"Please add it to experiment_config.yaml."
                )

        # Merge defaults with provided values (provided values take precedence)
        merged = {**_DEFAULTS, **d}

        # Coerce types
        dataset_path = Path(merged["dataset_path"])

        raw_size = merged["image_size"]
        if isinstance(raw_size, (list, tuple)) and len(raw_size) == 2:
            image_size = (int(raw_size[0]), int(raw_size[1]))
        else:
            raise ValueError(
                f"'image_size' must be a list of two integers [width, height], "
                f"got: {raw_size!r}"
            )

        gallery_ratio = float(merged["gallery_ratio"])
        if not (0.0 < gallery_ratio < 1.0):
            raise ValueError(
                f"'gallery_ratio' must be in (0, 1), got: {gallery_ratio}"
            )

        open_set_ratio = float(merged["open_set_ratio"])
        if not (0.0 <= open_set_ratio < 1.0):
            raise ValueError(
                f"'open_set_ratio' must be in [0, 1), got: {open_set_ratio}"
            )

        num_runs = int(merged["num_runs"])
        if num_runs < 1:
            raise ValueError(
                f"'num_runs' must be a positive integer, got: {num_runs}"
            )

        detectors = list(merged["detectors"])
        recognizers = list(merged["recognizers"])

        if not detectors:
            raise ValueError("'detectors' list must contain at least one entry.")
        if not recognizers:
            raise ValueError("'recognizers' list must contain at least one entry.")

        return cls(
            dataset_path=dataset_path,
            gallery_ratio=gallery_ratio,
            random_seed=int(merged["random_seed"]),
            image_size=image_size,
            detectors=detectors,
            recognizers=recognizers,
            similarity_threshold=float(merged["similarity_threshold"]),
            output_dir=Path(merged["output_dir"]),
            open_set_ratio=open_set_ratio,
            num_runs=num_runs,
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ExperimentConfig":
        """
        Load configuration from a YAML file.

        Args:
            path: Path to the YAML config file (absolute or relative to cwd).

        Returns:
            ExperimentConfig populated from the file.

        Raises:
            FileNotFoundError: If the YAML file does not exist.
            ValueError:        If a required key is missing or a value is invalid.
        """
        yaml_path = Path(path)
        if not yaml_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {yaml_path.resolve()}\n"
                f"Expected at: backend/evaluation/configs/experiment_config.yaml"
            )

        with yaml_path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        if raw is None:
            raise ValueError(f"Config file is empty: {yaml_path}")

        if not isinstance(raw, dict):
            raise ValueError(
                f"Config file must contain a YAML mapping (dict), "
                f"got {type(raw).__name__}: {yaml_path}"
            )

        return cls.from_dict(raw)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def resolve_output_dirs(self) -> None:
        """
        Create all required output sub-directories under output_dir if they
        do not already exist.  Call this once before starting experiments.
        """
        subdirs = [
            self.output_dir / "logs" / "failures",
            self.output_dir / "plots",
            self.output_dir / "reports",
        ]
        for d in subdirs:
            d.mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:
        return (
            f"ExperimentConfig(\n"
            f"  dataset_path={self.dataset_path},\n"
            f"  gallery_ratio={self.gallery_ratio},\n"
            f"  random_seed={self.random_seed},\n"
            f"  image_size={self.image_size},\n"
            f"  detectors={self.detectors},\n"
            f"  recognizers={self.recognizers},\n"
            f"  similarity_threshold={self.similarity_threshold},\n"
            f"  output_dir={self.output_dir},\n"
            f"  open_set_ratio={self.open_set_ratio},\n"
            f"  num_runs={self.num_runs},\n"
            f")"
        )
