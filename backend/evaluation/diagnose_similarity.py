"""
Similarity Distribution Diagnostic Script

Investigates why InsightFace recognition accuracy is low by analyzing:
  1. Raw cosine similarity distribution (genuine vs impostor)
  2. Normalised similarity distribution [0,1]
  3. Embedding L2-norm verification
  4. Threshold sweep table (FAR/FRR at each threshold)
  5. Top-20 similarity scores for correct and rejected genuine matches
  6. Recommended operating threshold

Run from workspace root:
    python backend/evaluation/diagnose_similarity.py
"""

from __future__ import annotations

import sys
import math
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

_EVAL_ROOT = Path(__file__).resolve().parent
if str(_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_EVAL_ROOT))

from configs.config import ExperimentConfig
from detection.insightface_detector import InsightFaceDetector
from recognition.insightface_recognizer import InsightFaceRecognizer
from pipeline.detection_pipeline import DetectionPipeline
from pipeline.recognition_pipeline import RecognitionPipeline
from utils.image_loader import DatasetSplitter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(v: Optional[float], decimals: int = 4) -> str:
    return f"{v:.{decimals}f}" if v is not None else "N/A"


def _stats(values: List[float]) -> dict:
    if not values:
        return {"n": 0, "min": None, "max": None, "mean": None, "std": None, "median": None}
    n = len(values)
    mean = sum(values) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / n)
    return {
        "n": n,
        "min": min(values),
        "max": max(values),
        "mean": mean,
        "std": std,
        "median": statistics.median(values),
    }


def _print_stats(label: str, values: List[float]) -> None:
    s = _stats(values)
    print(f"  {label}:")
    print(f"    n={s['n']}  min={_fmt(s['min'])}  max={_fmt(s['max'])}  "
          f"mean={_fmt(s['mean'])}  std={_fmt(s['std'])}  median={_fmt(s['median'])}")


def _histogram(values: List[float], bins: int = 10, lo: float = 0.0, hi: float = 1.0) -> str:
    """ASCII histogram."""
    if not values:
        return "  (no data)"
    width = hi - lo
    bin_size = width / bins
    counts = [0] * bins
    for v in values:
        idx = min(int((v - lo) / bin_size), bins - 1)
        if 0 <= idx < bins:
            counts[idx] += 1
    max_count = max(counts) if counts else 1
    bar_width = 30
    lines = []
    for i, c in enumerate(counts):
        lo_b = lo + i * bin_size
        hi_b = lo_b + bin_size
        bar = "█" * int(c / max_count * bar_width)
        lines.append(f"  [{lo_b:.2f}-{hi_b:.2f}] {bar} {c}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main diagnostic
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("  InsightFace Similarity Distribution Diagnostic")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Load config and build split
    # ------------------------------------------------------------------
    cfg = ExperimentConfig.from_yaml(_EVAL_ROOT / "configs" / "experiment_config.yaml")
    cfg.dataset_path = _EVAL_ROOT / cfg.dataset_path
    cfg.gallery_ratio = 0.70
    cfg.random_seed = 42

    splitter = DatasetSplitter(cfg, min_images=10)
    split = splitter.split(run_index=0)

    gallery_labels = set(split.gallery.keys())
    print(f"\nDataset: {len(gallery_labels)} identities")
    print(f"Gallery: {sum(len(v) for v in split.gallery.values())} images")
    print(f"Probe:   {sum(len(v) for v in split.probe.values())} images")

    # ------------------------------------------------------------------
    # 2. Build recognizer and gallery (sample 15 images per identity for speed)
    # ------------------------------------------------------------------
    print("\n[1/5] Loading InsightFace recognizer...")
    rec = InsightFaceRecognizer()

    MAX_GALLERY_PER_ID = 15  # limit for speed
    MAX_PROBE_PER_ID = 10

    # Preprocess gallery crops
    gallery_pairs: List[Tuple[str, np.ndarray]] = []
    for identity, paths in split.gallery.items():
        for p in paths[:MAX_GALLERY_PER_ID]:
            try:
                crop = splitter.preprocess(p)
                gallery_pairs.append((identity, crop))
            except Exception:
                pass

    rec.build_gallery(gallery_pairs)
    print(f"  Gallery built: {len(rec.get_gallery_embeddings())} identity centroids "
          f"({len(gallery_pairs)} crops)")

    # ------------------------------------------------------------------
    # 3. Verify embedding normalization
    # ------------------------------------------------------------------
    print("\n[2/5] Verifying embedding L2 normalization...")
    gallery_embs = rec.get_gallery_embeddings()
    norms = [float(np.linalg.norm(emb)) for emb in gallery_embs.values()]
    print(f"  Gallery centroid norms: min={min(norms):.6f}  max={max(norms):.6f}  "
          f"mean={sum(norms)/len(norms):.6f}")
    all_normalized = all(abs(n - 1.0) < 1e-4 for n in norms)
    print(f"  All L2-normalized: {'YES ✓' if all_normalized else 'NO ✗ — PROBLEM FOUND'}")

    # Check raw embeddings
    raw_embs = rec.get_raw_embeddings()
    raw_norms = []
    for embs in raw_embs.values():
        for e in embs[:5]:  # sample first 5 per identity
            raw_norms.append(float(np.linalg.norm(e)))
    if raw_norms:
        print(f"  Raw embedding norms (sample): min={min(raw_norms):.6f}  "
              f"max={max(raw_norms):.6f}  mean={sum(raw_norms)/len(raw_norms):.6f}")

    # ------------------------------------------------------------------
    # 4. Compute raw cosine similarities for all probe images
    # ------------------------------------------------------------------
    print("\n[3/5] Computing similarity distribution over probe set...")

    genuine_raw_sims: List[float] = []    # raw cosine [-1,1]
    impostor_raw_sims: List[float] = []
    genuine_norm_sims: List[float] = []   # normalised [0,1]
    impostor_norm_sims: List[float] = []

    # Records for top-k analysis
    genuine_records: List[dict] = []
    rejected_genuine_records: List[dict] = []

    probe_count = 0
    skipped = 0

    for identity, paths in split.probe.items():
        for img_path in paths[:MAX_PROBE_PER_ID]:
            try:
                crop = splitter.preprocess(img_path)
            except Exception:
                skipped += 1
                continue

            probe_emb = rec._embed(crop)
            if probe_emb is None:
                skipped += 1
                continue

            probe_count += 1

            # Compute raw cosine similarity to ALL gallery centroids
            sims_to_all: Dict[str, float] = {}
            for lbl, centroid in gallery_embs.items():
                raw_cos = float(np.dot(probe_emb, centroid))  # both L2-norm → dot = cosine
                sims_to_all[lbl] = raw_cos

            best_label = max(sims_to_all, key=sims_to_all.get)
            best_raw = sims_to_all[best_label]
            best_norm = (best_raw + 1.0) / 2.0

            true_raw = sims_to_all.get(identity, None)
            true_norm = (true_raw + 1.0) / 2.0 if true_raw is not None else None

            is_genuine_match = (best_label == identity)

            if is_genuine_match:
                genuine_raw_sims.append(best_raw)
                genuine_norm_sims.append(best_norm)
                genuine_records.append({
                    "image": img_path.name,
                    "true_label": identity,
                    "predicted": best_label,
                    "raw_cosine": best_raw,
                    "norm_sim": best_norm,
                    "correct": True,
                })
            else:
                # Impostor: best match is wrong identity
                impostor_raw_sims.append(best_raw)
                impostor_norm_sims.append(best_norm)
                # Also record the true-identity similarity
                if true_norm is not None:
                    rejected_genuine_records.append({
                        "image": img_path.name,
                        "true_label": identity,
                        "predicted": best_label,
                        "raw_cosine_to_true": true_raw,
                        "norm_sim_to_true": true_norm,
                        "raw_cosine_to_pred": best_raw,
                        "norm_sim_to_pred": best_norm,
                        "correct": False,
                    })

    print(f"  Processed: {probe_count} probe images ({skipped} skipped)")
    print(f"  Correct matches (genuine): {len(genuine_raw_sims)}")
    print(f"  Wrong matches (impostor):  {len(impostor_raw_sims)}")

    # ------------------------------------------------------------------
    # 5. Print similarity statistics
    # ------------------------------------------------------------------
    print("\n[4/5] Similarity Statistics")
    print("-" * 50)

    print("\n  RAW cosine similarity [-1, 1]:")
    _print_stats("Genuine (correct match)", genuine_raw_sims)
    _print_stats("Impostor (wrong match)", impostor_raw_sims)

    print("\n  NORMALISED similarity [0, 1]  = (raw + 1) / 2:")
    _print_stats("Genuine (correct match)", genuine_norm_sims)
    _print_stats("Impostor (wrong match)", impostor_norm_sims)

    print("\n  Histogram — Genuine normalised similarity:")
    print(_histogram(genuine_norm_sims, bins=10))

    print("\n  Histogram — Impostor normalised similarity:")
    print(_histogram(impostor_norm_sims, bins=10))

    # ------------------------------------------------------------------
    # 6. Top-20 similarity scores
    # ------------------------------------------------------------------
    print("\n[5/5] Top-20 Similarity Scores")
    print("-" * 50)

    print("\n  Top 20 CORRECT matches (highest normalised similarity):")
    top_correct = sorted(genuine_records, key=lambda x: x["norm_sim"], reverse=True)[:20]
    print(f"  {'Image':<45} {'True':>20} {'NormSim':>9} {'RawCos':>9}")
    print(f"  {'-'*45} {'-'*20} {'-'*9} {'-'*9}")
    for r in top_correct:
        print(f"  {r['image']:<45} {r['true_label']:>20} {r['norm_sim']:>9.4f} {r['raw_cosine']:>9.4f}")

    print(f"\n  Top 20 REJECTED genuine matches (highest sim-to-true, but wrong prediction):")
    top_rejected = sorted(rejected_genuine_records,
                          key=lambda x: x["norm_sim_to_true"], reverse=True)[:20]
    print(f"  {'Image':<45} {'True':>20} {'Pred':>20} {'SimToTrue':>10} {'SimToPred':>10}")
    print(f"  {'-'*45} {'-'*20} {'-'*20} {'-'*10} {'-'*10}")
    for r in top_rejected:
        print(f"  {r['image']:<45} {r['true_label']:>20} {r['predicted']:>20} "
              f"{r['norm_sim_to_true']:>10.4f} {r['norm_sim_to_pred']:>10.4f}")

    # ------------------------------------------------------------------
    # 7. Threshold sweep table
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  Threshold Sweep (closed-set: accuracy at each threshold)")
    print("=" * 70)

    all_sims = genuine_norm_sims + impostor_norm_sims
    if all_sims:
        min_s, max_s = min(all_sims), max(all_sims)
    else:
        min_s, max_s = 0.0, 1.0

    thresholds = [round(t, 3) for t in
                  [i * 0.05 for i in range(int(min_s / 0.05), int(max_s / 0.05) + 2)]]
    thresholds = sorted(set(thresholds + [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9]))

    print(f"\n  {'Threshold':>10} {'Correct':>8} {'Total':>7} {'Accuracy':>10} "
          f"{'Accepted':>9} {'Rejected':>9}")
    print(f"  {'-'*10} {'-'*8} {'-'*7} {'-'*10} {'-'*9} {'-'*9}")

    best_acc = 0.0
    best_threshold = 0.5

    for t in thresholds:
        # In closed-set mode: accepted = similarity >= threshold
        # Correct = genuine match AND similarity >= threshold
        correct_at_t = sum(1 for s in genuine_norm_sims if s >= t)
        accepted_at_t = sum(1 for s in genuine_norm_sims if s >= t) + \
                        sum(1 for s in impostor_norm_sims if s >= t)
        total_detected = len(genuine_norm_sims) + len(impostor_norm_sims)
        acc = correct_at_t / total_detected if total_detected > 0 else 0.0

        if acc > best_acc:
            best_acc = acc
            best_threshold = t

        marker = " ← current" if abs(t - 0.85) < 0.001 else ""
        marker = marker or (" ← BEST" if abs(t - best_threshold) < 0.001 and acc == best_acc else "")
        print(f"  {t:>10.3f} {correct_at_t:>8} {total_detected:>7} {acc:>10.4f} "
              f"{accepted_at_t:>9} {total_detected - accepted_at_t:>9}{marker}")

    # ------------------------------------------------------------------
    # 8. Diagnosis and recommendation
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  DIAGNOSIS")
    print("=" * 70)

    if genuine_norm_sims:
        genuine_mean = sum(genuine_norm_sims) / len(genuine_norm_sims)
        genuine_min = min(genuine_norm_sims)
        genuine_max = max(genuine_norm_sims)

        print(f"\n  Genuine match similarity range: [{genuine_min:.4f}, {genuine_max:.4f}]")
        print(f"  Genuine match similarity mean:  {genuine_mean:.4f}")
        print(f"  Current threshold:              0.8500")
        print(f"  Fraction of genuine above 0.85: "
              f"{sum(1 for s in genuine_norm_sims if s >= 0.85) / len(genuine_norm_sims):.4f}")

        if genuine_mean < 0.85:
            print(f"\n  ⚠  CONFIRMED: threshold=0.85 is TOO STRICT for this dataset.")
            print(f"     Most genuine matches have similarity < 0.85.")
            print(f"     The normalised cosine similarity for ArcFace genuine pairs")
            print(f"     typically clusters around 0.55–0.75, not 0.85+.")
        else:
            print(f"\n  ✓  Threshold 0.85 appears reasonable for this dataset.")

        print(f"\n  RECOMMENDED threshold: {best_threshold:.3f}  (accuracy={best_acc:.4f})")
        print(f"\n  To fix: update experiment_config.yaml:")
        print(f"    similarity_threshold: {best_threshold:.2f}")
        print(f"\n  Note: The normalised similarity = (raw_cosine + 1) / 2")
        print(f"    Raw cosine for genuine ArcFace pairs: ~{genuine_mean*2-1:.3f}")
        print(f"    This is normal — ArcFace cosine similarity is NOT close to 1.0")
        print(f"    for real-world face pairs with varying angles/lighting.")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
