"""
RecognitionMetrics — computes recognition evaluation metrics from PredictionRecords.

Formulas
--------
Accuracy  = |correct predictions| / |detected probes|
            (excludes missed detections from denominator)

FAR       = FP_impostor / N_impostor_attempts
            where FP_impostor = impostor probes incorrectly accepted
            N_impostor_attempts = total probes where true_label ∉ gallery

FRR       = (FN_genuine + missed_detections) / N_genuine_attempts
            where FN_genuine = genuine probes incorrectly rejected
            N_genuine_attempts = total probes where true_label ∈ gallery

EER       = threshold T* where FAR(T*) ≈ FRR(T*)
            found by sweeping ≥100 evenly spaced thresholds over [min_sim, max_sim]

Open-Set Detection Rate = |unknown probes correctly rejected| / |unknown probes|
False Alarm Rate        = |unknown probes incorrectly accepted| / |unknown probes|

Timing stats (per experiment):
  mean, median, std, min, max of detection_ms, recognition_ms, total_ms

Usage
-----
    from pipeline.recognition_pipeline import PredictionRecord
    from metrics.recognition_metrics import RecognitionMetrics

    gallery_labels = {"alice", "bob"}
    result = RecognitionMetrics.compute(predictions, gallery_labels)
    print(result)

    eer_result = RecognitionMetrics.compute_eer(predictions, gallery_labels)
    print(f"EER threshold: {eer_result.eer_threshold:.4f}, EER: {eer_result.eer:.4f}")
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from pipeline.recognition_pipeline import PredictionRecord


# ---------------------------------------------------------------------------
# RecognitionMetricsResult
# ---------------------------------------------------------------------------

@dataclass
class RecognitionMetricsResult:
    """
    Computed recognition metrics for one (detector, recognizer) experiment.

    Attributes:
        accuracy:          Correct / detected probes. None if no detected probes.
        far:               False Acceptance Rate. None if no impostor attempts.
        frr:               False Rejection Rate. None if no genuine attempts.
        tp:                True positives (genuine, correctly accepted).
        fp:                False positives (impostor, incorrectly accepted).
        tn:                True negatives (impostor, correctly rejected).
        fn:                False negatives (genuine, incorrectly rejected).
        missed_detections: Probes with no face detected.
        total_probes:      Total probe images.
        detected_probes:   Probes with ≥1 face detected.
        genuine_attempts:  Probes where true_label is in gallery.
        impostor_attempts: Probes where true_label is NOT in gallery.
        confusion_matrix:  Dict {true_label: {predicted_label: count}}.
        labels:            Sorted list of all identity labels seen.
        threshold:         Similarity threshold used.
        open_set_detection_rate: Fraction of unknown probes correctly rejected.
        false_alarm_rate:        Fraction of unknown probes incorrectly accepted.
    """
    accuracy: Optional[float]
    far: Optional[float]
    frr: Optional[float]
    tp: int
    fp: int
    tn: int
    fn: int
    missed_detections: int
    total_probes: int
    detected_probes: int
    genuine_attempts: int
    impostor_attempts: int
    confusion_matrix: Dict[str, Dict[str, int]]
    labels: List[str]
    threshold: float
    open_set_detection_rate: Optional[float] = None
    false_alarm_rate: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "accuracy": round(self.accuracy, 6) if self.accuracy is not None else None,
            "far": round(self.far, 6) if self.far is not None else None,
            "frr": round(self.frr, 6) if self.frr is not None else None,
            "tp": self.tp, "fp": self.fp, "tn": self.tn, "fn": self.fn,
            "missed_detections": self.missed_detections,
            "total_probes": self.total_probes,
            "detected_probes": self.detected_probes,
            "genuine_attempts": self.genuine_attempts,
            "impostor_attempts": self.impostor_attempts,
            "threshold": self.threshold,
            "open_set_detection_rate": self.open_set_detection_rate,
            "false_alarm_rate": self.false_alarm_rate,
        }

    def __str__(self) -> str:
        acc = f"{self.accuracy:.4f}" if self.accuracy is not None else "N/A"
        far = f"{self.far:.4f}"      if self.far      is not None else "N/A"
        frr = f"{self.frr:.4f}"      if self.frr      is not None else "N/A"
        osd = (f"{self.open_set_detection_rate:.4f}"
               if self.open_set_detection_rate is not None else "N/A")
        return (
            f"RecognitionMetrics("
            f"accuracy={acc}, FAR={far}, FRR={frr}, "
            f"TP={self.tp}, FP={self.fp}, TN={self.tn}, FN={self.fn}, "
            f"missed={self.missed_detections}, "
            f"open_set_detection_rate={osd}, "
            f"threshold={self.threshold:.4f})"
        )


@dataclass
class EERResult:
    """
    Equal Error Rate analysis result.

    Attributes:
        eer_threshold:  Threshold T* where |FAR(T*) - FRR(T*)| is minimised.
        eer:            The EER value = (FAR(T*) + FRR(T*)) / 2.
        accuracy_at_eer: Accuracy at the EER threshold.
        far_at_eer:     FAR at the EER threshold.
        frr_at_eer:     FRR at the EER threshold.
        sweep_thresholds: Array of threshold values swept.
        sweep_far:        FAR values at each threshold.
        sweep_frr:        FRR values at each threshold.
    """
    eer_threshold: float
    eer: float
    accuracy_at_eer: Optional[float]
    far_at_eer: Optional[float]
    frr_at_eer: Optional[float]
    sweep_thresholds: List[float]
    sweep_far: List[float]
    sweep_frr: List[float]

    def __str__(self) -> str:
        acc = f"{self.accuracy_at_eer:.4f}" if self.accuracy_at_eer is not None else "N/A"
        return (
            f"EERResult(eer_threshold={self.eer_threshold:.4f}, "
            f"eer={self.eer:.4f}, accuracy_at_eer={acc}, "
            f"far_at_eer={self.far_at_eer:.4f}, "
            f"frr_at_eer={self.frr_at_eer:.4f})"
        )


@dataclass
class TimingStats:
    """
    Timing statistics for one experiment.

    Attributes:
        mean_detection_ms:    Mean detection time per image.
        median_detection_ms:  Median detection time.
        std_detection_ms:     Std dev of detection time.
        min_detection_ms:     Minimum detection time.
        max_detection_ms:     Maximum detection time.
        (same for recognition_ms and total_ms)
    """
    mean_detection_ms: float
    median_detection_ms: float
    std_detection_ms: float
    min_detection_ms: float
    max_detection_ms: float

    mean_recognition_ms: float
    median_recognition_ms: float
    std_recognition_ms: float
    min_recognition_ms: float
    max_recognition_ms: float

    mean_total_ms: float
    median_total_ms: float
    std_total_ms: float
    min_total_ms: float
    max_total_ms: float

    n_samples: int

    def to_dict(self) -> dict:
        return {k: round(v, 4) if isinstance(v, float) else v
                for k, v in self.__dict__.items()}

    def __str__(self) -> str:
        return (
            f"TimingStats(n={self.n_samples}, "
            f"det={self.mean_detection_ms:.1f}±{self.std_detection_ms:.1f}ms, "
            f"rec={self.mean_recognition_ms:.1f}±{self.std_recognition_ms:.1f}ms, "
            f"total={self.mean_total_ms:.1f}±{self.std_total_ms:.1f}ms)"
        )


# ---------------------------------------------------------------------------
# RecognitionMetrics
# ---------------------------------------------------------------------------

class RecognitionMetrics:
    """
    Computes recognition evaluation metrics from PredictionRecords.
    """

    @staticmethod
    def compute(
        predictions: List[PredictionRecord],
        gallery_labels: Set[str],
        threshold: float = 0.5,
        open_set_labels: Optional[Set[str]] = None,
    ) -> RecognitionMetricsResult:
        """
        Compute recognition metrics at a fixed similarity threshold.

        Args:
            predictions:      Output of RecognitionPipeline.predict_probe().
            gallery_labels:   Set of identity labels enrolled in the gallery.
            threshold:        Similarity threshold. Predictions with
                              similarity < threshold are treated as rejections
                              for FAR/FRR computation.
            open_set_labels:  Set of identity labels that are NOT in the gallery
                              (open-set unknown identities). Used to compute
                              open_set_detection_rate and false_alarm_rate.

        Returns:
            RecognitionMetricsResult with all computed metrics.
        """
        if not predictions:
            return RecognitionMetricsResult(
                accuracy=None, far=None, frr=None,
                tp=0, fp=0, tn=0, fn=0,
                missed_detections=0, total_probes=0, detected_probes=0,
                genuine_attempts=0, impostor_attempts=0,
                confusion_matrix={}, labels=[],
                threshold=threshold,
            )

        open_set_labels = open_set_labels or set()
        all_labels = sorted(
            {p.true_label for p in predictions if p.true_label}
            | {p.predicted_label for p in predictions
               if p.predicted_label and p.predicted_label != "unknown"}
        )

        total = len(predictions)
        missed = sum(1 for p in predictions if not p.detected)
        detected = total - missed

        # Confusion matrix: {true_label: {predicted_label: count}}
        cm: Dict[str, Dict[str, int]] = {}
        for p in predictions:
            tl = p.true_label or "unknown"
            pl = p.predicted_label or "no_detection"
            cm.setdefault(tl, {})
            cm[tl][pl] = cm[tl].get(pl, 0) + 1

        # TP, FP, TN, FN, genuine/impostor counts
        tp = fp = tn = fn = 0
        genuine_attempts = 0
        impostor_attempts = 0

        for p in predictions:
            true_lbl = p.true_label
            pred_lbl = p.predicted_label

            is_genuine = true_lbl in gallery_labels
            is_impostor = true_lbl in open_set_labels or (
                true_lbl is not None and true_lbl not in gallery_labels
            )

            if is_genuine:
                genuine_attempts += 1
                # Accepted = detected AND predicted_label matches true_label
                # AND similarity >= threshold
                accepted = (
                    p.detected
                    and pred_lbl == true_lbl
                    and p.similarity >= threshold
                )
                if accepted:
                    tp += 1
                else:
                    fn += 1  # missed detection or wrong prediction or below threshold

            elif is_impostor:
                impostor_attempts += 1
                # Accepted = predicted_label is a gallery identity (not "unknown"/None)
                # AND similarity >= threshold
                accepted = (
                    p.detected
                    and pred_lbl is not None
                    and pred_lbl != "unknown"
                    and p.similarity >= threshold
                )
                if accepted:
                    fp += 1
                else:
                    tn += 1

        # Accuracy: correct / detected (excludes missed detections)
        correct = sum(
            1 for p in predictions
            if p.detected and p.predicted_label == p.true_label
        )
        accuracy = correct / detected if detected > 0 else None

        # FAR = FP / impostor_attempts
        far = fp / impostor_attempts if impostor_attempts > 0 else None

        # FRR = FN / genuine_attempts  (FN includes missed detections)
        frr = fn / genuine_attempts if genuine_attempts > 0 else None

        # Open-set metrics
        osd_rate = None
        fa_rate = None
        if open_set_labels:
            unknown_probes = [
                p for p in predictions if p.true_label in open_set_labels
            ]
            if unknown_probes:
                correctly_rejected = sum(
                    1 for p in unknown_probes
                    if p.predicted_label == "unknown" or not p.detected
                    or p.similarity < threshold
                )
                osd_rate = correctly_rejected / len(unknown_probes)
                fa_rate = 1.0 - osd_rate

        return RecognitionMetricsResult(
            accuracy=accuracy,
            far=far,
            frr=frr,
            tp=tp, fp=fp, tn=tn, fn=fn,
            missed_detections=missed,
            total_probes=total,
            detected_probes=detected,
            genuine_attempts=genuine_attempts,
            impostor_attempts=impostor_attempts,
            confusion_matrix=cm,
            labels=all_labels,
            threshold=threshold,
            open_set_detection_rate=osd_rate,
            false_alarm_rate=fa_rate,
        )

    @staticmethod
    def compute_eer(
        predictions: List[PredictionRecord],
        gallery_labels: Set[str],
        n_thresholds: int = 100,
        open_set_labels: Optional[Set[str]] = None,
    ) -> EERResult:
        """
        Compute the Equal Error Rate by sweeping similarity thresholds.

        Sweeps ≥ n_thresholds evenly spaced values over [min_sim, max_sim].
        The EER threshold T* minimises |FAR(T) - FRR(T)|.

        Args:
            predictions:    Output of RecognitionPipeline.predict_probe().
            gallery_labels: Set of gallery identity labels.
            n_thresholds:   Number of threshold values to sweep. Default 100.
            open_set_labels: Optional set of unknown identity labels.

        Returns:
            EERResult with EER threshold, EER value, and sweep arrays.
        """
        if not predictions:
            return EERResult(
                eer_threshold=0.5, eer=0.5,
                accuracy_at_eer=None, far_at_eer=None, frr_at_eer=None,
                sweep_thresholds=[], sweep_far=[], sweep_frr=[],
            )

        sims = [p.similarity for p in predictions]
        min_sim = min(sims)
        max_sim = max(sims)

        # Ensure at least n_thresholds steps; add small margin
        step = (max_sim - min_sim) / max(n_thresholds - 1, 1)
        thresholds = [min_sim + i * step for i in range(n_thresholds)]
        # Always include boundary values
        if thresholds[0] > 0.0:
            thresholds = [0.0] + thresholds
        if thresholds[-1] < 1.0:
            thresholds = thresholds + [1.0]

        sweep_far: List[float] = []
        sweep_frr: List[float] = []

        for t in thresholds:
            result = RecognitionMetrics.compute(
                predictions, gallery_labels, threshold=t,
                open_set_labels=open_set_labels,
            )
            sweep_far.append(result.far if result.far is not None else 0.0)
            sweep_frr.append(result.frr if result.frr is not None else 1.0)

        # Find threshold minimising |FAR - FRR|
        best_idx = min(
            range(len(thresholds)),
            key=lambda i: abs(sweep_far[i] - sweep_frr[i]),
        )
        eer_threshold = thresholds[best_idx]
        eer = (sweep_far[best_idx] + sweep_frr[best_idx]) / 2.0

        # Metrics at EER threshold
        eer_metrics = RecognitionMetrics.compute(
            predictions, gallery_labels, threshold=eer_threshold,
            open_set_labels=open_set_labels,
        )

        return EERResult(
            eer_threshold=eer_threshold,
            eer=eer,
            accuracy_at_eer=eer_metrics.accuracy,
            far_at_eer=eer_metrics.far,
            frr_at_eer=eer_metrics.frr,
            sweep_thresholds=thresholds,
            sweep_far=sweep_far,
            sweep_frr=sweep_frr,
        )

    @staticmethod
    def compute_timing_stats(
        predictions: List[PredictionRecord],
    ) -> TimingStats:
        """
        Compute timing statistics across all probe predictions.

        Args:
            predictions: List of PredictionRecord objects.

        Returns:
            TimingStats with mean/median/std/min/max for each timing field.
        """
        if not predictions:
            z = 0.0
            return TimingStats(
                mean_detection_ms=z, median_detection_ms=z,
                std_detection_ms=z, min_detection_ms=z, max_detection_ms=z,
                mean_recognition_ms=z, median_recognition_ms=z,
                std_recognition_ms=z, min_recognition_ms=z, max_recognition_ms=z,
                mean_total_ms=z, median_total_ms=z,
                std_total_ms=z, min_total_ms=z, max_total_ms=z,
                n_samples=0,
            )

        def _stats(values: List[float]) -> Tuple[float, float, float, float, float]:
            n = len(values)
            mean = sum(values) / n
            median = statistics.median(values)
            variance = sum((v - mean) ** 2 for v in values) / n
            std = math.sqrt(variance)
            return mean, median, std, min(values), max(values)

        det_ms  = [p.detection_ms   for p in predictions]
        rec_ms  = [p.recognition_ms for p in predictions]
        tot_ms  = [p.total_ms       for p in predictions]

        dm, dmed, dstd, dmin, dmax = _stats(det_ms)
        rm, rmed, rstd, rmin, rmax = _stats(rec_ms)
        tm, tmed, tstd, tmin, tmax = _stats(tot_ms)

        return TimingStats(
            mean_detection_ms=dm,   median_detection_ms=dmed,
            std_detection_ms=dstd,  min_detection_ms=dmin,  max_detection_ms=dmax,
            mean_recognition_ms=rm, median_recognition_ms=rmed,
            std_recognition_ms=rstd, min_recognition_ms=rmin, max_recognition_ms=rmax,
            mean_total_ms=tm,       median_total_ms=tmed,
            std_total_ms=tstd,      min_total_ms=tmin,       max_total_ms=tmax,
            n_samples=len(predictions),
        )

    @staticmethod
    def compute_confusion_matrix_array(
        confusion_matrix: Dict[str, Dict[str, int]],
        labels: List[str],
    ) -> "np.ndarray":
        """
        Convert the confusion matrix dict to a 2D numpy array.

        Rows = true labels, Columns = predicted labels.
        Order follows the sorted `labels` list.

        Args:
            confusion_matrix: {true_label: {predicted_label: count}}
            labels:           Sorted list of identity labels.

        Returns:
            numpy array of shape (N, N) where N = len(labels).
        """
        n = len(labels)
        label_idx = {lbl: i for i, lbl in enumerate(labels)}
        matrix = np.zeros((n, n), dtype=np.int32)

        for true_lbl, pred_counts in confusion_matrix.items():
            if true_lbl not in label_idx:
                continue
            ti = label_idx[true_lbl]
            for pred_lbl, count in pred_counts.items():
                if pred_lbl in label_idx:
                    pi = label_idx[pred_lbl]
                    matrix[ti, pi] += count

        return matrix
