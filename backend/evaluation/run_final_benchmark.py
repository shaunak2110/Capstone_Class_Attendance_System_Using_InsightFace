"""
Full Benchmark Matrix — 4 detector×recognizer combinations × 3 runs.

Combinations:
  1. haarcascade + lbph
  2. haarcascade + insightface
  3. insightface  + lbph
  4. insightface  + insightface

Outputs (results/final_benchmark/):
  predictions_<det>_<rec>_run<n>.csv
  metrics_<det>_<rec>_run<n>.json
  timing_<det>_<rec>_run<n>.json
  aggregated_summary.json
  final_comparison_table.txt

Run from workspace root:
    python backend/evaluation/run_final_benchmark.py
"""

from __future__ import annotations

import csv
import json
import logging
import math
import random
import statistics
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import cv2
import numpy as np

_EVAL_ROOT = Path(__file__).resolve().parent
if str(_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_EVAL_ROOT))

from configs.config import ExperimentConfig
from detection.haarcascade_detector import HaarcascadeDetector
from detection.insightface_detector import InsightFaceDetector
from metrics.detection_metrics import DetectionMetrics
from metrics.recognition_metrics import RecognitionMetrics
from pipeline.detection_pipeline import DetectionPipeline
from pipeline.recognition_pipeline import RecognitionPipeline
from recognition.insightface_recognizer import InsightFaceRecognizer
from utils.image_loader import DatasetSplitter

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATASET_PATH   = _EVAL_ROOT / "dataset" / "raw"
OUTPUT_DIR     = _EVAL_ROOT / "results" / "final_benchmark"
THRESHOLD      = 0.50
GALLERY_RATIO  = 0.70
BASE_SEED      = 42
NUM_RUNS       = 3
MIN_IMAGES     = 10
IMAGE_SIZE     = (640, 640)

COMBINATIONS = [
    ("haarcascade", "lbph"),
    ("haarcascade", "insightface"),
    ("insightface",  "lbph"),
    ("insightface",  "insightface"),
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
log_path = OUTPUT_DIR / "benchmark_log.txt"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(str(log_path), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("benchmark")

# ---------------------------------------------------------------------------
# Detector / Recognizer factories
# ---------------------------------------------------------------------------

def make_detector(name: str):
    if name == "haarcascade":
        return HaarcascadeDetector()
    elif name == "insightface":
        return InsightFaceDetector()
    raise ValueError(f"Unknown detector: {name}")


def make_recognizer(name: str):
    if name == "lbph":
        try:
            from recognition.lbph_recognizer import LBPHRecognizer
            return LBPHRecognizer()
        except ImportError:
            from recognition.lbph_recognizer import LBPHFallbackRecognizer
            log.warning("cv2.face unavailable — using LBPHFallbackRecognizer")
            return LBPHFallbackRecognizer()
    elif name == "insightface":
        return InsightFaceRecognizer()
    raise ValueError(f"Unknown recognizer: {name}")


# ---------------------------------------------------------------------------
# Single run
# ---------------------------------------------------------------------------

def run_single(
    det_name: str,
    rec_name: str,
    run_idx: int,
    cfg: ExperimentConfig,
) -> Optional[dict]:
    """
    Execute one (detector, recognizer, run_index) experiment.
    Returns a result dict or None on failure.
    """
    seed = BASE_SEED + run_idx
    exp_id = f"{det_name}_{rec_name}_run{run_idx}"
    log.info("  [%s] seed=%d", exp_id, seed)

    random.seed(seed)
    np.random.seed(seed)

    # Split
    splitter = DatasetSplitter(cfg, min_images=MIN_IMAGES)
    split = splitter.split(run_index=run_idx)
    gallery_labels: Set[str] = set(split.gallery.keys())

    # Gallery pairs
    gallery_pairs: List[Tuple[str, np.ndarray]] = []
    for identity, paths in split.gallery.items():
        for p in paths:
            try:
                crop = splitter.preprocess(p)
                gallery_pairs.append((identity, crop))
            except Exception:
                pass

    # Probe lists
    probe_images: List[str] = []
    probe_labels: List[str] = []
    for identity, paths in split.probe.items():
        for p in paths:
            probe_images.append(str(p))
            probe_labels.append(identity)

    # Instantiate models fresh per run (avoids gallery contamination)
    try:
        detector   = make_detector(det_name)
        recognizer = make_recognizer(rec_name)
    except Exception as exc:
        log.error("  [%s] model init failed: %s", exp_id, exc)
        return None

    # Detection
    det_pipeline = DetectionPipeline(detector, image_size=IMAGE_SIZE)
    det_records  = det_pipeline.run(probe_images, true_labels=probe_labels)

    # Recognition
    rec_pipeline = RecognitionPipeline(
        recognizer, threshold=THRESHOLD, open_set=False
    )
    rec_pipeline.build_gallery(gallery_pairs)
    predictions = rec_pipeline.predict_probe(det_records)

    # Metrics
    det_metrics  = DetectionMetrics.compute(det_records)
    rec_metrics  = RecognitionMetrics.compute(
        predictions, gallery_labels=gallery_labels, threshold=THRESHOLD
    )
    eer_result   = RecognitionMetrics.compute_eer(
        predictions, gallery_labels=gallery_labels, n_thresholds=100
    )
    timing_stats = RecognitionMetrics.compute_timing_stats(predictions)

    # Save predictions CSV
    csv_path = OUTPUT_DIR / f"predictions_{exp_id}.csv"
    if predictions:
        fieldnames = list(predictions[0].to_dict().keys())
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            for p in predictions:
                w.writerow(p.to_dict())

    # Save metrics JSON
    metrics_path = OUTPUT_DIR / f"metrics_{exp_id}.json"
    metrics_data = {
        "experiment_id": exp_id,
        "detector": det_name,
        "recognizer": rec_name,
        "run": run_idx,
        "seed": seed,
        "threshold": THRESHOLD,
        "detection": det_metrics.to_dict(),
        "recognition": rec_metrics.to_dict(),
        "eer": {
            "eer_threshold": round(eer_result.eer_threshold, 6),
            "eer": round(eer_result.eer, 6),
            "accuracy_at_eer": round(eer_result.accuracy_at_eer, 6) if eer_result.accuracy_at_eer is not None else None,
            "far_at_eer": round(eer_result.far_at_eer, 6) if eer_result.far_at_eer is not None else None,
            "frr_at_eer": round(eer_result.frr_at_eer, 6) if eer_result.frr_at_eer is not None else None,
        },
    }
    with metrics_path.open("w", encoding="utf-8") as fh:
        json.dump(metrics_data, fh, indent=2)

    # Save timing JSON
    timing_path = OUTPUT_DIR / f"timing_{exp_id}.json"
    with timing_path.open("w", encoding="utf-8") as fh:
        json.dump(timing_stats.to_dict(), fh, indent=2)

    acc = rec_metrics.accuracy
    frr = rec_metrics.frr
    log.info(
        "  [%s] det_rate=%.3f  acc=%.3f  frr=%s  eer=%.3f  "
        "total_ms=%.1f±%.1f",
        exp_id,
        det_metrics.detection_rate,
        acc if acc is not None else 0.0,
        f"{frr:.3f}" if frr is not None else "N/A",
        eer_result.eer,
        timing_stats.mean_total_ms,
        timing_stats.std_total_ms,
    )

    return {
        "experiment_id": exp_id,
        "detector": det_name,
        "recognizer": rec_name,
        "run": run_idx,
        "seed": seed,
        "status": "OK",
        "detection_rate": det_metrics.detection_rate,
        "accuracy": acc,
        "far": rec_metrics.far,
        "frr": frr,
        "eer": eer_result.eer,
        "eer_threshold": eer_result.eer_threshold,
        "mean_total_ms": timing_stats.mean_total_ms,
        "std_total_ms": timing_stats.std_total_ms,
        "mean_detection_ms": timing_stats.mean_detection_ms,
        "mean_recognition_ms": timing_stats.mean_recognition_ms,
        "total_probes": rec_metrics.total_probes,
        "detected_probes": rec_metrics.detected_probes,
    }


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _mean_std(values: List[Optional[float]]) -> Tuple[Optional[float], Optional[float]]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None, None
    n = len(vals)
    m = sum(vals) / n
    std = math.sqrt(sum((v - m) ** 2 for v in vals) / n) if n > 1 else 0.0
    return round(m, 4), round(std, 4)


def aggregate_runs(results: List[dict]) -> dict:
    """Aggregate metrics across multiple runs for one (det, rec) combination."""
    if not results:
        return {}
    det = results[0]["detector"]
    rec = results[0]["recognizer"]

    acc_mean, acc_std   = _mean_std([r["accuracy"]       for r in results])
    far_mean, far_std   = _mean_std([r["far"]            for r in results])
    frr_mean, frr_std   = _mean_std([r["frr"]            for r in results])
    eer_mean, eer_std   = _mean_std([r["eer"]            for r in results])
    det_mean, det_std   = _mean_std([r["detection_rate"] for r in results])
    lat_mean, lat_std   = _mean_std([r["mean_total_ms"]  for r in results])
    det_ms_mean, _      = _mean_std([r["mean_detection_ms"]   for r in results])
    rec_ms_mean, _      = _mean_std([r["mean_recognition_ms"] for r in results])

    return {
        "detector": det,
        "recognizer": rec,
        "n_runs": len(results),
        "accuracy_mean": acc_mean,   "accuracy_std": acc_std,
        "far_mean": far_mean,        "far_std": far_std,
        "frr_mean": frr_mean,        "frr_std": frr_std,
        "eer_mean": eer_mean,        "eer_std": eer_std,
        "detection_rate_mean": det_mean, "detection_rate_std": det_std,
        "latency_mean_ms": lat_mean, "latency_std_ms": lat_std,
        "detection_ms_mean": det_ms_mean,
        "recognition_ms_mean": rec_ms_mean,
        "per_run": results,
    }


# ---------------------------------------------------------------------------
# Comparison table
# ---------------------------------------------------------------------------

def print_comparison_table(aggregated: List[dict]) -> str:
    header = (
        f"\n{'Detector':<15} {'Recognizer':<15} "
        f"{'Accuracy':>10} {'EER':>8} {'DetRate':>9} "
        f"{'FAR':>8} {'FRR':>8} {'Latency(ms)':>12}"
    )
    sep = "-" * len(header)
    lines = [sep, header, sep]

    for a in aggregated:
        def fmt(m, s):
            if m is None:
                return "   N/A  "
            if s is not None and s > 0:
                return f"{m:.3f}±{s:.3f}"
            return f"{m:.3f}      "

        lines.append(
            f"{a['detector']:<15} {a['recognizer']:<15} "
            f"{fmt(a['accuracy_mean'], a['accuracy_std']):>10} "
            f"{fmt(a['eer_mean'], a['eer_std']):>8} "
            f"{fmt(a['detection_rate_mean'], a['detection_rate_std']):>9} "
            f"{fmt(a['far_mean'], a['far_std']):>8} "
            f"{fmt(a['frr_mean'], a['frr_std']):>8} "
            f"{fmt(a['latency_mean_ms'], a['latency_std_ms']):>12}"
        )
    lines.append(sep)
    table = "\n".join(lines)
    log.info(table)
    return table


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    wall_start = time.perf_counter()
    log.info("=" * 65)
    log.info("  Full Benchmark Matrix — %d combinations × %d runs",
             len(COMBINATIONS), NUM_RUNS)
    log.info("  Dataset:   %s", DATASET_PATH)
    log.info("  Threshold: %.2f", THRESHOLD)
    log.info("  Output:    %s", OUTPUT_DIR)
    log.info("=" * 65)

    cfg = ExperimentConfig.from_dict({
        "dataset_path": str(DATASET_PATH),
        "detectors":    ["haarcascade", "insightface"],
        "recognizers":  ["lbph", "insightface"],
        "gallery_ratio": GALLERY_RATIO,
        "random_seed":   BASE_SEED,
        "num_runs":      NUM_RUNS,
        "similarity_threshold": THRESHOLD,
        "output_dir":    str(OUTPUT_DIR),
        "image_size":    list(IMAGE_SIZE),
    })

    all_results: List[dict] = []
    aggregated:  List[dict] = []

    total = len(COMBINATIONS) * NUM_RUNS
    done  = 0

    for det_name, rec_name in COMBINATIONS:
        combo_label = f"{det_name} + {rec_name}"
        log.info("")
        log.info("━" * 65)
        log.info("  Combination: %s", combo_label)
        log.info("━" * 65)

        combo_results: List[dict] = []

        for run_idx in range(NUM_RUNS):
            done += 1
            log.info("  Run %d/%d  [%d/%d total]", run_idx + 1, NUM_RUNS, done, total)
            t0 = time.perf_counter()

            try:
                result = run_single(det_name, rec_name, run_idx, cfg)
            except Exception as exc:
                log.error("  FAILED: %s\n%s", exc, traceback.format_exc())
                result = None

            elapsed = time.perf_counter() - t0
            log.info("  Run %d done in %.1fs", run_idx + 1, elapsed)

            if result is not None:
                combo_results.append(result)
                all_results.append(result)

        if combo_results:
            agg = aggregate_runs(combo_results)
            aggregated.append(agg)
            log.info(
                "  %s — accuracy=%.3f±%.3f  EER=%.3f±%.3f  "
                "det_rate=%.3f  latency=%.1f±%.1fms",
                combo_label,
                agg["accuracy_mean"] or 0, agg["accuracy_std"] or 0,
                agg["eer_mean"] or 0,      agg["eer_std"] or 0,
                agg["detection_rate_mean"] or 0,
                agg["latency_mean_ms"] or 0, agg["latency_std_ms"] or 0,
            )

    # ------------------------------------------------------------------
    # Save aggregated summary
    # ------------------------------------------------------------------
    summary_path = OUTPUT_DIR / "aggregated_summary.json"
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(aggregated, fh, indent=2)
    log.info("\nAggregated summary saved: %s", summary_path)

    # ------------------------------------------------------------------
    # Print and save comparison table
    # ------------------------------------------------------------------
    log.info("\n" + "=" * 65)
    log.info("  FINAL COMPARISON TABLE  (mean ± std across %d runs)", NUM_RUNS)
    log.info("=" * 65)
    table = print_comparison_table(aggregated)

    table_path = OUTPUT_DIR / "final_comparison_table.txt"
    table_path.write_text(table, encoding="utf-8")
    log.info("Comparison table saved: %s", table_path)

    # ------------------------------------------------------------------
    # Best model
    # ------------------------------------------------------------------
    best = max(
        (a for a in aggregated if a["accuracy_mean"] is not None),
        key=lambda a: a["accuracy_mean"],
        default=None,
    )
    if best:
        log.info(
            "\n  Best combination: %s + %s  "
            "(accuracy=%.3f±%.3f, EER=%.3f, latency=%.1fms)",
            best["detector"], best["recognizer"],
            best["accuracy_mean"], best["accuracy_std"] or 0,
            best["eer_mean"] or 0,
            best["latency_mean_ms"] or 0,
        )

    total_wall = time.perf_counter() - wall_start
    log.info("\nTotal wall time: %.1fs (%.1f min)", total_wall, total_wall / 60)
    log.info("All outputs saved to: %s", OUTPUT_DIR)


if __name__ == "__main__":
    main()
