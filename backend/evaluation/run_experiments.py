"""
ExperimentRunner — orchestrates the full evaluation pipeline.

Flow per experiment (detector × recognizer × run):
  DatasetSplitter → DetectionPipeline → RecognitionPipeline → Metrics → Save

Outputs (under results/experiments/<timestamp>/):
  predictions_<det>_<rec>_run<n>.csv   — per-image predictions
  metrics_<det>_<rec>_run<n>.json      — recognition + detection metrics
  timing_<det>_<rec>_run<n>.json       — timing statistics
  eer_<det>_<rec>_run<n>.json          — EER sweep results
  summary.json                          — aggregated results across all experiments
  experiment_log.txt                    — full run log with timestamps

Usage (from backend/evaluation/):
    python run_experiments.py
    python run_experiments.py --config configs/experiment_config.yaml
    python run_experiments.py --detectors insightface haarcascade --recognizers insightface lbph
    python run_experiments.py --runs 3 --open-set-ratio 0.25
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import platform
import random
import sys
import time
import traceback
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

# Ensure backend/evaluation is on sys.path when run directly
_EVAL_ROOT = Path(__file__).resolve().parent
if str(_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_EVAL_ROOT))

from configs.config import ExperimentConfig
from detection import BaseDetector
from detection.haarcascade_detector import HaarcascadeDetector
from detection.insightface_detector import InsightFaceDetector
from metrics.detection_metrics import DetectionMetrics
from metrics.recognition_metrics import RecognitionMetrics
from pipeline.detection_pipeline import DetectionPipeline
from pipeline.recognition_pipeline import RecognitionPipeline
from recognition import BaseRecognizer
from recognition.insightface_recognizer import InsightFaceRecognizer
from utils.image_loader import DatasetSplitter, SplitResult

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("experiment_runner")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    # File handler
    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ---------------------------------------------------------------------------
# Detector / Recognizer registry
# ---------------------------------------------------------------------------

def _build_detector(name: str) -> Tuple[Optional[BaseDetector], Optional[str]]:
    """Instantiate a detector by name. Returns (detector, reason) tuple."""
    try:
        if name == "insightface":
            return InsightFaceDetector(), None
        elif name == "haarcascade":
            return HaarcascadeDetector(), None
        elif name == "retinaface":
            from detection.retinaface_detector import RetinaFaceDetector
            return RetinaFaceDetector(), None
        elif name == "yolo":
            from detection.yolo_detector import YOLODetector
            return YOLODetector(), None
        else:
            return None, f"Unknown detector: '{name}'"
    except (ImportError, FileNotFoundError) as exc:
        return None, str(exc)
    except Exception as exc:
        return None, str(exc)


def _build_recognizer(name: str) -> Optional[BaseRecognizer]:
    """Instantiate a recognizer by name. Returns (None, reason) if unavailable."""
    try:
        if name == "insightface":
            return InsightFaceRecognizer(), None
        elif name == "lbph":
            try:
                from recognition.lbph_recognizer import LBPHRecognizer
                return LBPHRecognizer(), None
            except ImportError:
                from recognition.lbph_recognizer import LBPHFallbackRecognizer
                return LBPHFallbackRecognizer(), "cv2.face unavailable, using numpy fallback"
        elif name == "dlib":
            from recognition.dlib_recognizer import DlibRecognizer
            return DlibRecognizer(), None
        else:
            raise ValueError(f"Unknown recognizer: '{name}'")
    except (ImportError, FileNotFoundError) as exc:
        return None, str(exc)
    except Exception as exc:
        return None, str(exc)


# ---------------------------------------------------------------------------
# ExperimentRunner
# ---------------------------------------------------------------------------

class ExperimentRunner:
    """
    Orchestrates all detector × recognizer × run experiments.

    Args:
        config:      ExperimentConfig controlling all parameters.
        output_dir:  Override output directory (defaults to config.output_dir).
        min_images:  Minimum images per identity for DatasetSplitter.
    """

    def __init__(
        self,
        config: ExperimentConfig,
        output_dir: Optional[Path] = None,
        min_images: int = 10,
    ) -> None:
        self._config = config
        self._min_images = min_images

        # Timestamped experiment directory
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = output_dir or config.output_dir
        self._exp_dir = Path(base) / "experiments" / ts
        self._exp_dir.mkdir(parents=True, exist_ok=True)

        self._logger = _setup_logging(self._exp_dir / "experiment_log.txt")
        self._summary: List[dict] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run_all(self) -> Path:
        """
        Run all detector × recognizer × run combinations.

        Returns:
            Path to the experiment output directory.
        """
        cfg = self._config
        self._log_header()

        # Set global random seeds for reproducibility
        random.seed(cfg.random_seed)
        np.random.seed(cfg.random_seed)

        # Build detector and recognizer instances (skip unavailable ones)
        detectors = self._load_detectors(cfg.detectors)
        recognizers = self._load_recognizers(cfg.recognizers)

        if not detectors:
            self._logger.error("No detectors available. Aborting.")
            return self._exp_dir
        if not recognizers:
            self._logger.error("No recognizers available. Aborting.")
            return self._exp_dir

        total_experiments = len(detectors) * len(recognizers) * cfg.num_runs
        self._logger.info(
            "Starting %d experiments (%d detectors × %d recognizers × %d runs)",
            total_experiments, len(detectors), len(recognizers), cfg.num_runs,
        )

        exp_count = 0
        wall_start = time.perf_counter()

        for run_idx in range(cfg.num_runs):
            effective_seed = cfg.random_seed + run_idx
            self._logger.info("=" * 60)
            self._logger.info("RUN %d/%d  (seed=%d)", run_idx + 1, cfg.num_runs, effective_seed)
            self._logger.info("=" * 60)

            # Build split for this run
            splitter = DatasetSplitter(cfg, min_images=self._min_images)
            try:
                split = splitter.split(run_index=run_idx)
            except Exception as exc:
                self._logger.error("DatasetSplitter failed for run %d: %s", run_idx, exc)
                continue

            gallery_labels = set(split.gallery.keys())
            open_set_labels = set(split.open_set_identities)

            self._logger.info(
                "Split: %d gallery identities, %d probe identities, "
                "%d open-set identities",
                len(gallery_labels),
                len(split.probe),
                len(open_set_labels),
            )

            for det_name, detector in detectors.items():
                for rec_name, recognizer in recognizers.items():
                    exp_count += 1
                    exp_id = f"{det_name}_{rec_name}_run{run_idx}"
                    self._logger.info(
                        "[%d/%d] Experiment: %s", exp_count, total_experiments, exp_id
                    )
                    t_exp_start = time.perf_counter()

                    try:
                        self._run_single_experiment(
                            split=split,
                            detector=detector,
                            recognizer=recognizer,
                            det_name=det_name,
                            rec_name=rec_name,
                            run_idx=run_idx,
                            gallery_labels=gallery_labels,
                            open_set_labels=open_set_labels,
                        )
                    except Exception as exc:
                        tb = traceback.format_exc()
                        self._logger.error(
                            "Experiment %s FAILED:\n%s", exp_id, tb
                        )
                        self._summary.append({
                            "experiment_id": exp_id,
                            "detector": det_name,
                            "recognizer": rec_name,
                            "run": run_idx,
                            "status": "FAILED",
                            "error": str(exc),
                        })
                        continue

                    elapsed = (time.perf_counter() - t_exp_start)
                    self._logger.info(
                        "[%d/%d] %s completed in %.1fs",
                        exp_count, total_experiments, exp_id, elapsed,
                    )

        total_wall = time.perf_counter() - wall_start
        self._logger.info("=" * 60)
        self._logger.info(
            "All experiments complete. Total wall time: %.1fs (%.1f min)",
            total_wall, total_wall / 60,
        )

        # Save summary
        self._save_summary()
        self._logger.info("Results saved to: %s", self._exp_dir)
        return self._exp_dir

    # ------------------------------------------------------------------
    # Single experiment
    # ------------------------------------------------------------------

    def _run_single_experiment(
        self,
        split: SplitResult,
        detector: BaseDetector,
        recognizer: BaseRecognizer,
        det_name: str,
        rec_name: str,
        run_idx: int,
        gallery_labels: Set[str],
        open_set_labels: Set[str],
    ) -> None:
        cfg = self._config
        exp_id = f"{det_name}_{rec_name}_run{run_idx}"

        # ------------------------------------------------------------------
        # 1. Build gallery pairs from split
        # ------------------------------------------------------------------
        gallery_pairs: List[Tuple[str, Path]] = []
        for identity, paths in split.gallery.items():
            for p in paths:
                gallery_pairs.append((identity, p))

        # ------------------------------------------------------------------
        # 2. Build probe list
        # ------------------------------------------------------------------
        probe_images: List[Path] = []
        probe_labels: List[str] = []
        for identity, paths in split.probe.items():
            for p in paths:
                probe_images.append(p)
                probe_labels.append(identity)

        self._logger.info(
            "  Gallery: %d crops across %d identities | Probe: %d images",
            len(gallery_pairs), len(split.gallery), len(probe_images),
        )

        # ------------------------------------------------------------------
        # 3. Detection pipeline
        # ------------------------------------------------------------------
        det_pipeline = DetectionPipeline(
            detector=detector,
            image_size=cfg.image_size,
        )
        det_records = det_pipeline.run(
            images=[str(p) for p in probe_images],
            true_labels=probe_labels,
        )

        # ------------------------------------------------------------------
        # 4. Recognition pipeline — build gallery
        # ------------------------------------------------------------------
        rec_pipeline = RecognitionPipeline(
            recognizer=recognizer,
            threshold=cfg.similarity_threshold,
            open_set=len(open_set_labels) > 0,
        )

        # Load gallery crops (use DatasetSplitter.preprocess for consistency)
        splitter = DatasetSplitter(cfg, min_images=self._min_images)
        gallery_crop_pairs: List[Tuple[str, np.ndarray]] = []
        for identity, img_path in gallery_pairs:
            try:
                crop = splitter.preprocess(img_path)
                gallery_crop_pairs.append((identity, crop))
            except Exception as exc:
                self._logger.debug(
                    "  Skipping gallery image %s: %s", img_path.name, exc
                )

        rec_pipeline.build_gallery(gallery_crop_pairs)

        # ------------------------------------------------------------------
        # 5. Recognition pipeline — predict probe
        # ------------------------------------------------------------------
        predictions = rec_pipeline.predict_probe(det_records)

        # ------------------------------------------------------------------
        # 6. Compute metrics
        # ------------------------------------------------------------------
        det_metrics = DetectionMetrics.compute(det_records)
        rec_metrics = RecognitionMetrics.compute(
            predictions,
            gallery_labels=gallery_labels,
            threshold=cfg.similarity_threshold,
            open_set_labels=open_set_labels if open_set_labels else None,
        )
        eer_result = RecognitionMetrics.compute_eer(
            predictions,
            gallery_labels=gallery_labels,
            n_thresholds=100,
            open_set_labels=open_set_labels if open_set_labels else None,
        )
        timing_stats = RecognitionMetrics.compute_timing_stats(predictions)

        # ------------------------------------------------------------------
        # 7. Log metrics
        # ------------------------------------------------------------------
        acc_str = f"{rec_metrics.accuracy:.4f}" if rec_metrics.accuracy is not None else "N/A"
        far_str = f"{rec_metrics.far:.4f}"      if rec_metrics.far      is not None else "N/A"
        frr_str = f"{rec_metrics.frr:.4f}"      if rec_metrics.frr      is not None else "N/A"
        self._logger.info(
            "  Detection rate: %.4f | Accuracy: %s | FAR: %s | FRR: %s | EER: %.4f",
            det_metrics.detection_rate, acc_str, far_str, frr_str, eer_result.eer,
        )
        self._logger.info(
            "  Timing: det=%.1f±%.1fms  rec=%.1f±%.1fms  total=%.1f±%.1fms",
            timing_stats.mean_detection_ms, timing_stats.std_detection_ms,
            timing_stats.mean_recognition_ms, timing_stats.std_recognition_ms,
            timing_stats.mean_total_ms, timing_stats.std_total_ms,
        )

        # ------------------------------------------------------------------
        # 8. Save outputs
        # ------------------------------------------------------------------
        self._save_predictions_csv(predictions, exp_id)
        self._save_metrics_json(det_metrics, rec_metrics, eer_result, exp_id)
        self._save_timing_json(timing_stats, exp_id)

        # ------------------------------------------------------------------
        # 9. Append to summary
        # ------------------------------------------------------------------
        self._summary.append({
            "experiment_id": exp_id,
            "detector": det_name,
            "recognizer": rec_name,
            "run": run_idx,
            "status": "OK",
            "detection_rate": round(det_metrics.detection_rate, 6),
            "accuracy": round(rec_metrics.accuracy, 6) if rec_metrics.accuracy is not None else None,
            "far": round(rec_metrics.far, 6) if rec_metrics.far is not None else None,
            "frr": round(rec_metrics.frr, 6) if rec_metrics.frr is not None else None,
            "eer": round(eer_result.eer, 6),
            "eer_threshold": round(eer_result.eer_threshold, 6),
            "mean_total_ms": round(timing_stats.mean_total_ms, 3),
            "total_probes": rec_metrics.total_probes,
            "detected_probes": rec_metrics.detected_probes,
            "missed_detections": rec_metrics.missed_detections,
        })

    # ------------------------------------------------------------------
    # Save helpers
    # ------------------------------------------------------------------

    def _save_predictions_csv(self, predictions, exp_id: str) -> None:
        path = self._exp_dir / f"predictions_{exp_id}.csv"
        if not predictions:
            return
        fieldnames = list(predictions[0].to_dict().keys())
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for p in predictions:
                writer.writerow(p.to_dict())
        self._logger.debug("  Saved predictions: %s", path.name)

    def _save_metrics_json(self, det_metrics, rec_metrics, eer_result, exp_id: str) -> None:
        path = self._exp_dir / f"metrics_{exp_id}.json"
        data = {
            "detection": det_metrics.to_dict(),
            "recognition": rec_metrics.to_dict(),
            "eer": {
                "eer_threshold": round(eer_result.eer_threshold, 6),
                "eer": round(eer_result.eer, 6),
                "accuracy_at_eer": round(eer_result.accuracy_at_eer, 6) if eer_result.accuracy_at_eer is not None else None,
                "far_at_eer": round(eer_result.far_at_eer, 6) if eer_result.far_at_eer is not None else None,
                "frr_at_eer": round(eer_result.frr_at_eer, 6) if eer_result.frr_at_eer is not None else None,
                "sweep_thresholds": [round(t, 6) for t in eer_result.sweep_thresholds],
                "sweep_far": [round(f, 6) for f in eer_result.sweep_far],
                "sweep_frr": [round(f, 6) for f in eer_result.sweep_frr],
            },
        }
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        self._logger.debug("  Saved metrics: %s", path.name)

    def _save_timing_json(self, timing_stats, exp_id: str) -> None:
        path = self._exp_dir / f"timing_{exp_id}.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(timing_stats.to_dict(), fh, indent=2)
        self._logger.debug("  Saved timing: %s", path.name)

    def _save_summary(self) -> None:
        path = self._exp_dir / "summary.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self._summary, fh, indent=2)
        self._logger.info("Summary saved: %s", path.name)

        # Also print a compact table to console
        self._print_summary_table()

    def _print_summary_table(self) -> None:
        ok = [s for s in self._summary if s.get("status") == "OK"]
        if not ok:
            return
        header = f"\n{'Detector':<15} {'Recognizer':<15} {'Run':>3} {'DetRate':>8} {'Accuracy':>9} {'FAR':>8} {'FRR':>8} {'EER':>8} {'TotalMs':>9}"
        sep = "-" * len(header)
        self._logger.info(sep)
        self._logger.info(header)
        self._logger.info(sep)
        for s in ok:
            acc = f"{s['accuracy']:.4f}" if s['accuracy'] is not None else "  N/A  "
            far = f"{s['far']:.4f}"      if s['far']      is not None else "  N/A  "
            frr = f"{s['frr']:.4f}"      if s['frr']      is not None else "  N/A  "
            self._logger.info(
                f"{s['detector']:<15} {s['recognizer']:<15} {s['run']:>3} "
                f"{s['detection_rate']:>8.4f} {acc:>9} {far:>8} {frr:>8} "
                f"{s['eer']:>8.4f} {s['mean_total_ms']:>9.1f}"
            )
        self._logger.info(sep)

    # ------------------------------------------------------------------
    # Detector / Recognizer loading
    # ------------------------------------------------------------------

    def _load_detectors(self, names: List[str]) -> Dict[str, BaseDetector]:
        loaded = {}
        for name in names:
            det, reason = _build_detector(name)
            if det is None:
                self._logger.warning(
                    "Detector '%s' unavailable — skipping. Reason: %s", name, reason
                )
            else:
                loaded[name] = det
                if reason:
                    self._logger.info("Loaded detector: %s (%s)", name, reason)
                else:
                    self._logger.info("Loaded detector: %s", name)
        return loaded

    def _load_recognizers(self, names: List[str]) -> Dict[str, BaseRecognizer]:
        loaded = {}
        for name in names:
            rec, reason = _build_recognizer(name)
            if rec is None:
                self._logger.warning(
                    "Recognizer '%s' unavailable — skipping. Reason: %s", name, reason
                )
            else:
                loaded[name] = rec
                if reason:
                    self._logger.info("Loaded recognizer: %s (%s)", name, reason)
                else:
                    self._logger.info("Loaded recognizer: %s", name)
        return loaded

    # ------------------------------------------------------------------
    # Header logging
    # ------------------------------------------------------------------

    def _log_header(self) -> None:
        cfg = self._config
        self._logger.info("=" * 60)
        self._logger.info("Face Recognition Evaluation Pipeline")
        self._logger.info("=" * 60)
        self._logger.info("Python:      %s", sys.version.split()[0])
        self._logger.info("Platform:    %s", platform.platform())
        self._logger.info("Dataset:     %s", cfg.dataset_path)
        self._logger.info("Gallery:     %.0f%%", cfg.gallery_ratio * 100)
        self._logger.info("Seed:        %d", cfg.random_seed)
        self._logger.info("Runs:        %d", cfg.num_runs)
        self._logger.info("Open-set:    %.0f%%", cfg.open_set_ratio * 100)
        self._logger.info("Threshold:   %.2f", cfg.similarity_threshold)
        self._logger.info("Detectors:   %s", cfg.detectors)
        self._logger.info("Recognizers: %s", cfg.recognizers)
        self._logger.info("Output:      %s", self._exp_dir)
        self._logger.info("=" * 60)

        # Log library versions
        try:
            import cv2
            self._logger.info("opencv:      %s", cv2.__version__)
        except Exception:
            pass
        try:
            import insightface
            self._logger.info("insightface: %s", insightface.__version__)
        except Exception:
            pass
        try:
            import numpy
            self._logger.info("numpy:       %s", numpy.__version__)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Face Recognition Evaluation Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config",
        default="configs/experiment_config.yaml",
        help="Path to experiment config YAML",
    )
    parser.add_argument(
        "--detectors",
        nargs="+",
        help="Override detectors list (e.g. insightface haarcascade)",
    )
    parser.add_argument(
        "--recognizers",
        nargs="+",
        help="Override recognizers list (e.g. insightface lbph)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        help="Override num_runs",
    )
    parser.add_argument(
        "--open-set-ratio",
        type=float,
        dest="open_set_ratio",
        help="Override open_set_ratio (0.0–1.0)",
    )
    parser.add_argument(
        "--gallery-ratio",
        type=float,
        dest="gallery_ratio",
        help="Override gallery_ratio (0.0–1.0)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Override random_seed",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        help="Override output directory",
    )
    parser.add_argument(
        "--min-images",
        type=int,
        default=10,
        dest="min_images",
        help="Minimum images per identity",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Load config
    config_path = Path(args.config)
    if not config_path.is_absolute():
        # Resolve relative to the script's directory
        config_path = _EVAL_ROOT / config_path

    cfg = ExperimentConfig.from_yaml(config_path)

    # Apply CLI overrides
    if args.detectors:
        cfg.detectors = args.detectors
    if args.recognizers:
        cfg.recognizers = args.recognizers
    if args.runs is not None:
        cfg.num_runs = args.runs
    if args.open_set_ratio is not None:
        cfg.open_set_ratio = args.open_set_ratio
    if args.gallery_ratio is not None:
        cfg.gallery_ratio = args.gallery_ratio
    if args.seed is not None:
        cfg.random_seed = args.seed
    if args.output_dir:
        cfg.output_dir = Path(args.output_dir)

    # Resolve output dir relative to eval root if not absolute
    if not cfg.output_dir.is_absolute():
        cfg.output_dir = _EVAL_ROOT / cfg.output_dir

    # Resolve dataset path relative to eval root if not absolute
    if not cfg.dataset_path.is_absolute():
        cfg.dataset_path = _EVAL_ROOT / cfg.dataset_path

    runner = ExperimentRunner(cfg, min_images=args.min_images)
    exp_dir = runner.run_all()
    print(f"\nExperiment results saved to: {exp_dir}")


if __name__ == "__main__":
    main()
