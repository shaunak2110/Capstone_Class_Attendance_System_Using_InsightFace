"""
DatasetSplitter — identity-wise gallery/probe split with open-set support.

Handles real-world constraints:
  - Imbalanced identities (50–300+ images per person)
  - Configurable minimum image threshold per identity
  - Guaranteed ≥1 image in both gallery and probe per identity
  - Open-set mode: withheld identities appear only in probe
  - Reproducible splits via seeded RNG
  - Optional annotations.json and conditions.json per identity folder

Usage (from backend/evaluation/):
    from configs.config import ExperimentConfig
    from utils.image_loader import DatasetSplitter

    cfg = ExperimentConfig.from_yaml("configs/experiment_config.yaml")
    splitter = DatasetSplitter(cfg)
    result = splitter.split(run_index=0)
    splitter.print_summary(result)
"""

from __future__ import annotations

import json
import logging
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)

# ---------------------------------------------------------------------------
# Supported image extensions (case-insensitive)
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSIONS: frozenset = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp"}
)

# Default minimum images required per identity to be included in the split.
DEFAULT_MIN_IMAGES: int = 10


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class IdentityStats:
    """Per-identity image counts after splitting."""
    identity: str
    total_images: int
    gallery_count: int
    probe_count: int
    is_open_set: bool = False


@dataclass
class SplitResult:
    """
    Output of DatasetSplitter.split().

    Attributes:
        gallery:             {prn: [Path, ...]} — images used to build gallery embeddings.
        probe:               {prn: [Path, ...]} — images used for recognition testing.
                             Open-set identities appear here only (not in gallery).
        open_set_identities: List of identity labels withheld from the gallery.
        annotations:         {prn: {filename: [[x1,y1,x2,y2], ...]}} — loaded from
                             annotations.json if present; empty dict otherwise.
        conditions:          {prn: {filename: {"lighting": str, "angle": str}}} —
                             loaded from conditions.json if present; empty dict otherwise.
        stats:               Per-identity split statistics.
        run_index:           The run index used to generate this split.
        seed_used:           Effective random seed (config.random_seed + run_index).
    """
    gallery: Dict[str, List[Path]]
    probe: Dict[str, List[Path]]
    open_set_identities: List[str]
    annotations: Dict[str, Dict[str, List[List[int]]]]
    conditions: Dict[str, Dict[str, Dict[str, str]]]
    stats: List[IdentityStats]
    run_index: int
    seed_used: int


# ---------------------------------------------------------------------------
# DatasetSplitter
# ---------------------------------------------------------------------------

class DatasetSplitter:
    """
    Splits a raw image dataset into gallery and probe sets, identity by identity.

    Directory layout expected:
        <dataset_path>/
            <identity_1>/
                img001.jpg
                img002.jpg
                annotations.json   (optional)
                conditions.json    (optional)
            <identity_2>/
                ...

    Args:
        config:     ExperimentConfig controlling split behaviour.
        min_images: Minimum number of images an identity must have to be included.
                    Identities below this threshold are skipped with a warning.
                    Defaults to DEFAULT_MIN_IMAGES (10).
    """

    def __init__(self, config, min_images: int = DEFAULT_MIN_IMAGES) -> None:
        self._config = config
        self._min_images = min_images
        self._dataset_path = Path(config.dataset_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def split(self, run_index: int = 0) -> SplitResult:
        """
        Perform an identity-wise gallery/probe split.

        For each qualifying identity:
          - Shuffle images with seed = config.random_seed + run_index
          - Assign floor(N * gallery_ratio) images to gallery (min 1)
          - Assign remaining images to probe (min 1)

        Open-set identities (selected by open_set_ratio) are excluded from
        the gallery entirely; all their images go to probe.

        Args:
            run_index: Zero-based run index. Different values produce different
                       splits while remaining reproducible.

        Returns:
            SplitResult with gallery, probe, open_set_identities, and metadata.

        Raises:
            FileNotFoundError: If dataset_path does not exist.
            ValueError:        If no qualifying identities are found.
        """
        if not self._dataset_path.exists():
            raise FileNotFoundError(
                f"Dataset path not found: {self._dataset_path.resolve()}\n"
                f"Place images under: {self._dataset_path}/\n"
                f"Each sub-folder should be named with an identity label (e.g. PRN)."
            )

        effective_seed = self._config.random_seed + run_index
        rng = random.Random(effective_seed)

        # ------------------------------------------------------------------
        # 1. Discover all identity sub-folders
        # ------------------------------------------------------------------
        all_identities = sorted(
            p.name for p in self._dataset_path.iterdir()
            if p.is_dir()
        )

        if not all_identities:
            raise ValueError(
                f"No identity sub-folders found under: {self._dataset_path.resolve()}"
            )

        # ------------------------------------------------------------------
        # 2. Filter identities by minimum image count
        # ------------------------------------------------------------------
        qualified: List[str] = []
        skipped: List[Tuple[str, int]] = []

        for identity in all_identities:
            images = self._collect_images(identity)
            count = len(images)
            if count < self._min_images:
                skipped.append((identity, count))
            else:
                qualified.append(identity)

        for identity, count in skipped:
            logger.warning(
                "Skipping identity '%s': only %d image(s) found "
                "(minimum required: %d).",
                identity, count, self._min_images,
            )

        if not qualified:
            raise ValueError(
                f"No identities meet the minimum image threshold of "
                f"{self._min_images}. Found {len(skipped)} identities, all skipped."
            )

        # ------------------------------------------------------------------
        # 3. Select open-set identities (withheld from gallery)
        # ------------------------------------------------------------------
        open_set_identities: List[str] = []
        if self._config.open_set_ratio > 0.0:
            n_open = math.floor(len(qualified) * self._config.open_set_ratio)
            if n_open > 0:
                # Use a deterministic shuffle of qualified list for open-set selection
                shuffled_for_open = qualified.copy()
                rng.shuffle(shuffled_for_open)
                open_set_identities = sorted(shuffled_for_open[:n_open])
                logger.info(
                    "Open-set mode: %d/%d identities withheld from gallery: %s",
                    n_open, len(qualified), open_set_identities,
                )

        open_set_set = set(open_set_identities)

        # ------------------------------------------------------------------
        # 4. Split each identity
        # ------------------------------------------------------------------
        gallery: Dict[str, List[Path]] = {}
        probe: Dict[str, List[Path]] = {}
        stats: List[IdentityStats] = []
        annotations: Dict[str, Dict] = {}
        conditions: Dict[str, Dict] = {}

        for identity in qualified:
            images = self._collect_images(identity)
            # Shuffle with per-identity seed for reproducibility
            identity_seed = effective_seed + hash(identity) % (2**31)
            identity_rng = random.Random(identity_seed)
            identity_rng.shuffle(images)

            is_open = identity in open_set_set

            if is_open:
                # Open-set: all images go to probe only
                probe[identity] = images
                gallery_count = 0
                probe_count = len(images)
            else:
                # Closed-set: split by gallery_ratio, guarantee ≥1 in each partition
                n_total = len(images)
                n_gallery = max(1, math.floor(n_total * self._config.gallery_ratio))
                # Ensure at least 1 image remains for probe
                n_gallery = min(n_gallery, n_total - 1)

                gallery[identity] = images[:n_gallery]
                probe[identity] = images[n_gallery:]
                gallery_count = n_gallery
                probe_count = n_total - n_gallery

            stats.append(IdentityStats(
                identity=identity,
                total_images=len(images),
                gallery_count=gallery_count,
                probe_count=probe_count,
                is_open_set=is_open,
            ))

            # Load optional metadata files
            ann = self._load_annotations(identity)
            if ann:
                annotations[identity] = ann

            cond = self._load_conditions(identity)
            if cond:
                conditions[identity] = cond

        result = SplitResult(
            gallery=gallery,
            probe=probe,
            open_set_identities=open_set_identities,
            annotations=annotations,
            conditions=conditions,
            stats=stats,
            run_index=run_index,
            seed_used=effective_seed,
        )

        self._log_summary(result)
        return result

    def preprocess(self, image_path: Path) -> np.ndarray:
        """
        Load and preprocess a single image for detection/recognition.

        Steps:
          1. Load as BGR (OpenCV default)
          2. Resize to config.image_size (width × height)
          3. Clip pixel values to [0, 255] and cast to uint8

        Args:
            image_path: Absolute or relative path to the image file.

        Returns:
            BGR numpy array of shape (height, width, 3), dtype uint8.

        Raises:
            FileNotFoundError: If the image file does not exist.
            ValueError:        If OpenCV cannot decode the file.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path.resolve()}")

        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError(
                f"OpenCV could not decode image: {path}\n"
                f"Ensure the file is a valid image (jpg/png/bmp)."
            )

        w, h = self._config.image_size
        resized = cv2.resize(bgr, (w, h), interpolation=cv2.INTER_LINEAR)
        clipped = np.clip(resized, 0, 255).astype(np.uint8)
        return clipped

    def print_summary(self, result: SplitResult) -> None:
        """
        Print a human-readable split summary to stdout.

        Includes:
          - Total identities discovered / qualified / skipped
          - Per-identity image counts (gallery / probe)
          - Open-set identities
          - Grand totals
        """
        self._log_summary(result, force_print=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_images(self, identity: str) -> List[Path]:
        """Return sorted list of supported image paths for an identity."""
        identity_dir = self._dataset_path / identity
        images = sorted(
            p for p in identity_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        return images

    def _load_annotations(
        self, identity: str
    ) -> Optional[Dict[str, List[List[int]]]]:
        """
        Load bounding box annotations from annotations.json if present.

        Format: {"image_filename.jpg": [[x1, y1, x2, y2], ...], ...}

        Returns None if file absent; logs warning if file is malformed JSON.
        """
        ann_path = self._dataset_path / identity / "annotations.json"
        if not ann_path.exists():
            return None
        try:
            with ann_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("Root element must be a JSON object.")
            return data
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Malformed annotations.json for identity '%s': %s. "
                "Treating as unannotated.",
                identity, exc,
            )
            return None

    def _load_conditions(
        self, identity: str
    ) -> Optional[Dict[str, Dict[str, str]]]:
        """
        Load condition tags from conditions.json if present.

        Format: {"image_filename.jpg": {"lighting": "bright", "angle": "frontal"}, ...}

        Returns None if file absent; logs warning if file is malformed JSON.
        """
        cond_path = self._dataset_path / identity / "conditions.json"
        if not cond_path.exists():
            return None
        try:
            with cond_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("Root element must be a JSON object.")
            return data
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Malformed conditions.json for identity '%s': %s. "
                "Treating as unconditioned.",
                identity, exc,
            )
            return None

    def _log_summary(self, result: SplitResult, force_print: bool = False) -> None:
        """Log (and optionally print) a structured split summary."""
        total_gallery = sum(len(v) for v in result.gallery.values())
        total_probe = sum(len(v) for v in result.probe.values())
        total_images = total_gallery + total_probe
        n_closed = len(result.gallery)
        n_open = len(result.open_set_identities)
        n_total = len(result.stats)

        lines = [
            "",
            "=" * 60,
            "  DATASET SPLIT SUMMARY",
            "=" * 60,
            f"  Run index      : {result.run_index}",
            f"  Random seed    : {result.seed_used}",
            f"  Dataset path   : {self._dataset_path}",
            f"  Min images/id  : {self._min_images}",
            "-" * 60,
            f"  Identities     : {n_total} total  "
            f"({n_closed} closed-set, {n_open} open-set)",
            f"  Gallery images : {total_gallery}",
            f"  Probe images   : {total_probe}",
            f"  Total images   : {total_images}",
        ]

        if result.open_set_identities:
            lines.append(f"  Open-set IDs   : {result.open_set_identities}")

        lines.append("-" * 60)
        lines.append(
            f"  {'Identity':<20} {'Total':>6} {'Gallery':>8} {'Probe':>6} {'Type':>10}"
        )
        lines.append(f"  {'-'*20} {'-'*6} {'-'*8} {'-'*6} {'-'*10}")

        for s in sorted(result.stats, key=lambda x: x.identity):
            kind = "open-set" if s.is_open_set else "closed"
            lines.append(
                f"  {s.identity:<20} {s.total_images:>6} "
                f"{s.gallery_count:>8} {s.probe_count:>6} {kind:>10}"
            )

        lines.append("=" * 60)
        summary = "\n".join(lines)

        if force_print:
            print(summary)
        else:
            logger.info(summary)
