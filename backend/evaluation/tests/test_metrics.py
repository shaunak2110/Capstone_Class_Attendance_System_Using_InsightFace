"""
Tests for DetectionMetrics and RecognitionMetrics.

All tests use synthetic PredictionRecord / DetectionRecord data — no model
files or real images required.

Run from workspace root:
    python -m pytest backend/evaluation/tests/test_metrics.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import numpy as np
import pytest

_EVAL_ROOT = Path(__file__).resolve().parent.parent
if str(_EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(_EVAL_ROOT))

from detection import DetectionResult
from pipeline.detection_pipeline import DetectionRecord
from pipeline.recognition_pipeline import PredictionRecord
from metrics.detection_metrics import DetectionMetrics, DetectionMetricsResult, compute_iou
from metrics.recognition_metrics import (
    RecognitionMetrics, RecognitionMetricsResult, EERResult, TimingStats,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _det_record(
    image_id: str = "img.jpg",
    true_label: str = "alice",
    n_detections: int = 1,
    gt_boxes: Optional[List[List[int]]] = None,
    det_boxes: Optional[List[List[int]]] = None,
) -> DetectionRecord:
    """Build a DetectionRecord with synthetic detections."""
    crop = np.zeros((50, 50, 3), dtype=np.uint8)
    if det_boxes is not None:
        dets = [DetectionResult(bbox=b, confidence=0.9, crop=crop) for b in det_boxes]
    else:
        dets = [
            DetectionResult(bbox=[10, 10, 60, 60], confidence=0.9, crop=crop)
            for _ in range(n_detections)
        ]
    return DetectionRecord(
        image_id=image_id,
        true_label=true_label,
        detections=dets,
        detected=len(dets) > 0,
        detection_ms=5.0,
        ground_truth_boxes=gt_boxes,
        image_shape=(100, 100),
    )


def _pred(
    image_id: str = "img.jpg",
    true_label: str = "alice",
    predicted_label: str = "alice",
    similarity: float = 0.8,
    detected: bool = True,
    is_unknown: bool = False,
    detection_ms: float = 5.0,
    recognition_ms: float = 3.0,
) -> PredictionRecord:
    return PredictionRecord(
        image_id=image_id,
        true_label=true_label,
        predicted_label=predicted_label,
        similarity=similarity,
        detected=detected,
        is_unknown=is_unknown,
        detection_ms=detection_ms,
        recognition_ms=recognition_ms,
        total_ms=detection_ms + recognition_ms,
    )


# ---------------------------------------------------------------------------
# compute_iou tests
# ---------------------------------------------------------------------------

class TestComputeIoU:
    def test_identical_boxes_iou_one(self):
        box = [10, 10, 60, 60]
        assert abs(compute_iou(box, box) - 1.0) < 1e-6

    def test_non_overlapping_boxes_iou_zero(self):
        a = [0, 0, 10, 10]
        b = [20, 20, 30, 30]
        assert compute_iou(a, b) == 0.0

    def test_symmetric(self):
        a = [0, 0, 50, 50]
        b = [25, 25, 75, 75]
        assert abs(compute_iou(a, b) - compute_iou(b, a)) < 1e-9

    def test_iou_in_range(self):
        a = [0, 0, 50, 50]
        b = [25, 25, 75, 75]
        iou = compute_iou(a, b)
        assert 0.0 <= iou <= 1.0

    def test_partial_overlap(self):
        # 25x25 overlap out of 50x50 + 50x50 - 25x25 = 4375 union
        a = [0, 0, 50, 50]
        b = [25, 25, 75, 75]
        expected = (25 * 25) / (50 * 50 + 50 * 50 - 25 * 25)
        assert abs(compute_iou(a, b) - expected) < 1e-6

    def test_degenerate_box_zero(self):
        a = [10, 10, 10, 10]  # zero area
        b = [0, 0, 50, 50]
        assert compute_iou(a, b) == 0.0

    def test_contained_box(self):
        outer = [0, 0, 100, 100]
        inner = [25, 25, 75, 75]
        iou = compute_iou(outer, inner)
        # inner area = 2500, outer area = 10000, union = 10000
        expected = 2500 / 10000
        assert abs(iou - expected) < 1e-6


# ---------------------------------------------------------------------------
# DetectionMetrics tests
# ---------------------------------------------------------------------------

class TestDetectionMetrics:
    def test_empty_records_returns_zero_metrics(self):
        result = DetectionMetrics.compute([])
        assert result.total_images == 0
        assert result.detection_rate == 0.0

    def test_all_detected_rate_one(self):
        records = [_det_record(n_detections=1) for _ in range(5)]
        result = DetectionMetrics.compute(records)
        assert result.detection_rate == 1.0

    def test_none_detected_rate_zero(self):
        records = [_det_record(n_detections=0) for _ in range(5)]
        result = DetectionMetrics.compute(records)
        assert result.detection_rate == 0.0

    def test_partial_detection_rate(self):
        records = (
            [_det_record(n_detections=1)] * 3 +
            [_det_record(n_detections=0)] * 2
        )
        result = DetectionMetrics.compute(records)
        assert abs(result.detection_rate - 0.6) < 1e-9

    def test_approximate_mode_when_no_gt(self):
        records = [_det_record(n_detections=1) for _ in range(4)]
        result = DetectionMetrics.compute(records)
        assert result.gt_available is False
        # All single detections → precision = 1.0
        assert result.precision == 1.0

    def test_approximate_precision_with_extra_detections(self):
        # 2 images with 1 detection, 2 with 2 detections
        records = (
            [_det_record(n_detections=1)] * 2 +
            [_det_record(n_detections=2)] * 2
        )
        result = DetectionMetrics.compute(records)
        # precision ≈ 2/4 = 0.5
        assert abs(result.precision - 0.5) < 1e-9

    def test_iou_based_mode_when_gt_present(self):
        gt = [[10, 10, 60, 60]]
        det = [[10, 10, 60, 60]]  # perfect match
        records = [_det_record(gt_boxes=gt, det_boxes=det)]
        result = DetectionMetrics.compute(records, iou_threshold=0.5)
        assert result.gt_available is True
        assert result.tp == 1
        assert result.fp == 0
        assert result.fn == 0
        assert result.precision == 1.0
        assert result.recall == 1.0

    def test_iou_based_fp_when_no_gt_match(self):
        gt = [[0, 0, 10, 10]]
        det = [[80, 80, 100, 100]]  # no overlap
        records = [_det_record(gt_boxes=gt, det_boxes=det)]
        result = DetectionMetrics.compute(records, iou_threshold=0.5)
        assert result.tp == 0
        assert result.fp == 1
        assert result.fn == 1

    def test_iou_based_fn_when_no_detection(self):
        gt = [[10, 10, 60, 60]]
        records = [_det_record(gt_boxes=gt, det_boxes=[])]
        result = DetectionMetrics.compute(records, iou_threshold=0.5)
        assert result.fn == 1
        assert result.tp == 0

    def test_detection_rate_in_range(self):
        records = [_det_record(n_detections=i % 2) for i in range(10)]
        result = DetectionMetrics.compute(records)
        assert 0.0 <= result.detection_rate <= 1.0

    def test_to_dict_has_required_keys(self):
        result = DetectionMetrics.compute([_det_record()])
        d = result.to_dict()
        assert "detection_rate" in d
        assert "precision" in d
        assert "recall" in d


# ---------------------------------------------------------------------------
# RecognitionMetrics — basic tests
# ---------------------------------------------------------------------------

class TestRecognitionMetricsBasic:
    def test_empty_predictions_returns_none_metrics(self):
        result = RecognitionMetrics.compute([], {"alice"})
        assert result.accuracy is None
        assert result.far is None
        assert result.frr is None

    def test_perfect_accuracy(self):
        preds = [
            _pred("img1.jpg", "alice", "alice", 0.9),
            _pred("img2.jpg", "bob",   "bob",   0.85),
            _pred("img3.jpg", "alice", "alice", 0.88),
        ]
        result = RecognitionMetrics.compute(preds, {"alice", "bob"})
        assert result.accuracy == 1.0

    def test_zero_accuracy(self):
        preds = [
            _pred("img1.jpg", "alice", "bob",   0.9),
            _pred("img2.jpg", "bob",   "alice", 0.85),
        ]
        result = RecognitionMetrics.compute(preds, {"alice", "bob"})
        assert result.accuracy == 0.0

    def test_partial_accuracy(self):
        preds = [
            _pred("img1.jpg", "alice", "alice", 0.9),   # correct
            _pred("img2.jpg", "alice", "bob",   0.85),  # wrong
            _pred("img3.jpg", "bob",   "bob",   0.88),  # correct
            _pred("img4.jpg", "bob",   "alice", 0.7),   # wrong
        ]
        result = RecognitionMetrics.compute(preds, {"alice", "bob"})
        assert abs(result.accuracy - 0.5) < 1e-9

    def test_missed_detection_excluded_from_accuracy_denominator(self):
        preds = [
            _pred("img1.jpg", "alice", "alice", 0.9, detected=True),
            _pred("img2.jpg", "alice", None,    0.0, detected=False),  # missed
        ]
        result = RecognitionMetrics.compute(preds, {"alice"})
        # Only 1 detected probe; 1 correct → accuracy = 1.0
        assert result.accuracy == 1.0
        assert result.missed_detections == 1

    def test_missed_detection_counts_toward_frr(self):
        preds = [
            _pred("img1.jpg", "alice", "alice", 0.9, detected=True),
            _pred("img2.jpg", "alice", None,    0.0, detected=False),  # missed
        ]
        result = RecognitionMetrics.compute(preds, {"alice"})
        # 2 genuine attempts; 1 FN (missed) → FRR = 0.5
        assert abs(result.frr - 0.5) < 1e-9

    def test_total_probes_count(self):
        preds = [_pred() for _ in range(7)]
        result = RecognitionMetrics.compute(preds, {"alice"})
        assert result.total_probes == 7

    def test_confusion_matrix_populated(self):
        preds = [
            _pred("img1.jpg", "alice", "alice", 0.9),
            _pred("img2.jpg", "alice", "bob",   0.6),
            _pred("img3.jpg", "bob",   "bob",   0.85),
        ]
        result = RecognitionMetrics.compute(preds, {"alice", "bob"})
        assert result.confusion_matrix["alice"]["alice"] == 1
        assert result.confusion_matrix["alice"]["bob"] == 1
        assert result.confusion_matrix["bob"]["bob"] == 1

    def test_to_dict_has_required_keys(self):
        preds = [_pred()]
        result = RecognitionMetrics.compute(preds, {"alice"})
        d = result.to_dict()
        for key in ["accuracy", "far", "frr", "tp", "fp", "tn", "fn",
                    "missed_detections", "total_probes", "threshold"]:
            assert key in d


# ---------------------------------------------------------------------------
# FAR / FRR tests
# ---------------------------------------------------------------------------

class TestFARFRR:
    def test_far_zero_when_no_impostors(self):
        preds = [_pred("img1.jpg", "alice", "alice", 0.9)]
        result = RecognitionMetrics.compute(preds, {"alice"})
        # No impostor attempts → FAR is None
        assert result.far is None

    def test_frr_zero_when_all_genuine_accepted(self):
        preds = [
            _pred("img1.jpg", "alice", "alice", 0.9),
            _pred("img2.jpg", "alice", "alice", 0.85),
        ]
        result = RecognitionMetrics.compute(preds, {"alice"}, threshold=0.5)
        assert result.frr == 0.0

    def test_frr_one_when_all_genuine_rejected(self):
        # All below threshold → all FN
        preds = [
            _pred("img1.jpg", "alice", "alice", 0.1),
            _pred("img2.jpg", "alice", "alice", 0.2),
        ]
        result = RecognitionMetrics.compute(preds, {"alice"}, threshold=0.9)
        assert result.frr == 1.0

    def test_far_with_impostors(self):
        # 2 impostor probes: 1 accepted (sim >= threshold), 1 rejected
        preds = [
            _pred("img1.jpg", "charlie", "alice", 0.8, detected=True),  # FP
            _pred("img2.jpg", "charlie", "alice", 0.3, detected=True),  # TN (below threshold)
        ]
        result = RecognitionMetrics.compute(
            preds, {"alice"}, threshold=0.5,
            open_set_labels={"charlie"},
        )
        # 1 FP out of 2 impostor attempts → FAR = 0.5
        assert abs(result.far - 0.5) < 1e-9

    def test_far_frr_in_range(self):
        preds = [
            _pred("img1.jpg", "alice", "alice", 0.9),
            _pred("img2.jpg", "bob",   "alice", 0.7),
        ]
        result = RecognitionMetrics.compute(
            preds, {"alice"}, threshold=0.5,
            open_set_labels={"bob"},
        )
        if result.far is not None:
            assert 0.0 <= result.far <= 1.0
        if result.frr is not None:
            assert 0.0 <= result.frr <= 1.0


# ---------------------------------------------------------------------------
# Open-set tests
# ---------------------------------------------------------------------------

class TestOpenSetMetrics:
    def test_open_set_detection_rate_all_rejected(self):
        # All unknown probes correctly rejected (predicted "unknown" or below threshold)
        preds = [
            _pred("img1.jpg", "charlie", "unknown", 0.2, is_unknown=True),
            _pred("img2.jpg", "charlie", "unknown", 0.1, is_unknown=True),
        ]
        result = RecognitionMetrics.compute(
            preds, {"alice"}, threshold=0.5,
            open_set_labels={"charlie"},
        )
        assert result.open_set_detection_rate == 1.0
        assert result.false_alarm_rate == 0.0

    def test_open_set_detection_rate_all_accepted(self):
        # All unknown probes incorrectly accepted
        preds = [
            _pred("img1.jpg", "charlie", "alice", 0.9, is_unknown=False),
            _pred("img2.jpg", "charlie", "alice", 0.85, is_unknown=False),
        ]
        result = RecognitionMetrics.compute(
            preds, {"alice"}, threshold=0.5,
            open_set_labels={"charlie"},
        )
        assert result.open_set_detection_rate == 0.0
        assert result.false_alarm_rate == 1.0

    def test_open_set_rates_sum_to_one(self):
        preds = [
            _pred("img1.jpg", "charlie", "unknown", 0.2, is_unknown=True),
            _pred("img2.jpg", "charlie", "alice",   0.9, is_unknown=False),
        ]
        result = RecognitionMetrics.compute(
            preds, {"alice"}, threshold=0.5,
            open_set_labels={"charlie"},
        )
        assert result.open_set_detection_rate is not None
        assert result.false_alarm_rate is not None
        assert abs(result.open_set_detection_rate + result.false_alarm_rate - 1.0) < 1e-9

    def test_no_open_set_labels_returns_none_rates(self):
        preds = [_pred()]
        result = RecognitionMetrics.compute(preds, {"alice"})
        assert result.open_set_detection_rate is None
        assert result.false_alarm_rate is None


# ---------------------------------------------------------------------------
# EER tests
# ---------------------------------------------------------------------------

class TestEER:
    def _make_preds_for_eer(self) -> List[PredictionRecord]:
        """Synthetic predictions with a range of similarity scores."""
        preds = []
        # Genuine pairs: high similarity
        for i in range(5):
            preds.append(_pred(f"g{i}.jpg", "alice", "alice", 0.7 + i * 0.05))
        # Impostor pairs: low similarity
        for i in range(5):
            preds.append(_pred(f"imp{i}.jpg", "bob", "alice", 0.2 + i * 0.05))
        return preds

    def test_eer_result_type(self):
        preds = self._make_preds_for_eer()
        result = RecognitionMetrics.compute_eer(
            preds, {"alice"}, open_set_labels={"bob"}
        )
        assert isinstance(result, EERResult)

    def test_eer_threshold_in_range(self):
        preds = self._make_preds_for_eer()
        result = RecognitionMetrics.compute_eer(
            preds, {"alice"}, open_set_labels={"bob"}
        )
        assert 0.0 <= result.eer_threshold <= 1.0

    def test_eer_value_in_range(self):
        preds = self._make_preds_for_eer()
        result = RecognitionMetrics.compute_eer(
            preds, {"alice"}, open_set_labels={"bob"}
        )
        assert 0.0 <= result.eer <= 1.0

    def test_sweep_length_at_least_n_thresholds(self):
        preds = self._make_preds_for_eer()
        result = RecognitionMetrics.compute_eer(
            preds, {"alice"}, n_thresholds=100, open_set_labels={"bob"}
        )
        assert len(result.sweep_thresholds) >= 100

    def test_sweep_far_frr_same_length(self):
        preds = self._make_preds_for_eer()
        result = RecognitionMetrics.compute_eer(
            preds, {"alice"}, open_set_labels={"bob"}
        )
        assert len(result.sweep_far) == len(result.sweep_thresholds)
        assert len(result.sweep_frr) == len(result.sweep_thresholds)

    def test_eer_minimises_far_frr_difference(self):
        """EER threshold should minimise |FAR - FRR| over all swept thresholds."""
        preds = self._make_preds_for_eer()
        result = RecognitionMetrics.compute_eer(
            preds, {"alice"}, open_set_labels={"bob"}
        )
        best_diff = abs(result.far_at_eer - result.frr_at_eer)
        for far, frr in zip(result.sweep_far, result.sweep_frr):
            assert abs(far - frr) >= best_diff - 1e-9

    def test_empty_predictions_returns_default_eer(self):
        result = RecognitionMetrics.compute_eer([], {"alice"})
        assert result.eer_threshold == 0.5
        assert result.eer == 0.5

    def test_threshold_edge_zero(self):
        """At threshold=0, all probes accepted → FAR=1, FRR=0."""
        preds = [
            _pred("g1.jpg", "alice", "alice", 0.9),
            _pred("imp1.jpg", "bob", "alice", 0.3),
        ]
        result = RecognitionMetrics.compute(
            preds, {"alice"}, threshold=0.0,
            open_set_labels={"bob"},
        )
        # All accepted → FAR = 1.0, FRR = 0.0
        assert result.far == 1.0
        assert result.frr == 0.0

    def test_threshold_edge_one(self):
        """At threshold=1.0, all probes rejected → FAR=0, FRR=1."""
        preds = [
            _pred("g1.jpg", "alice", "alice", 0.9),
            _pred("imp1.jpg", "bob", "alice", 0.3),
        ]
        result = RecognitionMetrics.compute(
            preds, {"alice"}, threshold=1.0,
            open_set_labels={"bob"},
        )
        assert result.far == 0.0
        assert result.frr == 1.0


# ---------------------------------------------------------------------------
# Timing stats tests
# ---------------------------------------------------------------------------

class TestTimingStats:
    def test_empty_predictions_returns_zeros(self):
        stats = RecognitionMetrics.compute_timing_stats([])
        assert stats.n_samples == 0
        assert stats.mean_total_ms == 0.0

    def test_single_prediction_stats(self):
        p = _pred(detection_ms=10.0, recognition_ms=5.0)
        stats = RecognitionMetrics.compute_timing_stats([p])
        assert stats.mean_detection_ms == 10.0
        assert stats.mean_recognition_ms == 5.0
        assert stats.mean_total_ms == 15.0
        assert stats.std_detection_ms == 0.0
        assert stats.min_detection_ms == stats.max_detection_ms == 10.0

    def test_min_le_median_le_mean_le_max(self):
        preds = [
            _pred(detection_ms=1.0, recognition_ms=2.0),
            _pred(detection_ms=5.0, recognition_ms=3.0),
            _pred(detection_ms=10.0, recognition_ms=1.0),
            _pred(detection_ms=2.0, recognition_ms=4.0),
        ]
        stats = RecognitionMetrics.compute_timing_stats(preds)
        assert stats.min_detection_ms <= stats.median_detection_ms
        assert stats.median_detection_ms <= stats.max_detection_ms
        assert stats.min_recognition_ms <= stats.median_recognition_ms
        assert stats.median_recognition_ms <= stats.max_recognition_ms
        assert stats.min_total_ms <= stats.median_total_ms
        assert stats.median_total_ms <= stats.max_total_ms

    def test_std_zero_when_all_equal(self):
        preds = [_pred(detection_ms=5.0, recognition_ms=3.0) for _ in range(5)]
        stats = RecognitionMetrics.compute_timing_stats(preds)
        assert abs(stats.std_detection_ms) < 1e-9
        assert abs(stats.std_recognition_ms) < 1e-9

    def test_std_non_negative(self):
        preds = [
            _pred(detection_ms=1.0, recognition_ms=2.0),
            _pred(detection_ms=10.0, recognition_ms=5.0),
        ]
        stats = RecognitionMetrics.compute_timing_stats(preds)
        assert stats.std_detection_ms >= 0.0
        assert stats.std_recognition_ms >= 0.0
        assert stats.std_total_ms >= 0.0

    def test_n_samples_correct(self):
        preds = [_pred() for _ in range(7)]
        stats = RecognitionMetrics.compute_timing_stats(preds)
        assert stats.n_samples == 7

    def test_to_dict_has_all_keys(self):
        preds = [_pred()]
        stats = RecognitionMetrics.compute_timing_stats(preds)
        d = stats.to_dict()
        for key in [
            "mean_detection_ms", "median_detection_ms", "std_detection_ms",
            "min_detection_ms", "max_detection_ms",
            "mean_recognition_ms", "mean_total_ms", "n_samples",
        ]:
            assert key in d


# ---------------------------------------------------------------------------
# Confusion matrix array test
# ---------------------------------------------------------------------------

class TestConfusionMatrixArray:
    def test_shape_matches_labels(self):
        preds = [
            _pred("img1.jpg", "alice", "alice", 0.9),
            _pred("img2.jpg", "bob",   "alice", 0.7),
            _pred("img3.jpg", "bob",   "bob",   0.85),
        ]
        result = RecognitionMetrics.compute(preds, {"alice", "bob"})
        matrix = RecognitionMetrics.compute_confusion_matrix_array(
            result.confusion_matrix, result.labels
        )
        n = len(result.labels)
        assert matrix.shape == (n, n)

    def test_diagonal_correct_predictions(self):
        preds = [
            _pred("img1.jpg", "alice", "alice", 0.9),
            _pred("img2.jpg", "bob",   "bob",   0.85),
        ]
        result = RecognitionMetrics.compute(preds, {"alice", "bob"})
        matrix = RecognitionMetrics.compute_confusion_matrix_array(
            result.confusion_matrix, result.labels
        )
        # Diagonal should be non-zero for correct predictions
        assert matrix.diagonal().sum() >= 2

    def test_row_sums_match_per_identity_counts(self):
        preds = [
            _pred("img1.jpg", "alice", "alice", 0.9),
            _pred("img2.jpg", "alice", "bob",   0.6),
            _pred("img3.jpg", "bob",   "bob",   0.85),
        ]
        result = RecognitionMetrics.compute(preds, {"alice", "bob"})
        matrix = RecognitionMetrics.compute_confusion_matrix_array(
            result.confusion_matrix, result.labels
        )
        labels = result.labels
        alice_idx = labels.index("alice")
        # alice has 2 probe images → row sum = 2
        assert matrix[alice_idx].sum() == 2
