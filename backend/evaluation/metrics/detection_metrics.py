"""
DetectionMetrics — computes face detection evaluation metrics from DetectionRecords.

Formulas
--------
IoU(A, B)       = area(A ∩ B) / area(A ∪ B)
                  ∈ [0, 1]; symmetric; IoU(A,A) = 1.0

Detection Rate  = |images with ≥1 detection| / |total images|

When GT boxes are available (IoU-based):
  TP = detected boxes matched to a GT box with IoU ≥ iou_threshold
  FP = detected boxes with no matching GT box
  FN = GT boxes with no matching detected box
  Precision = TP / (TP + FP)   [0 if TP+FP=0]
  Recall    = TP / (TP + FN)   [0 if TP+FN=0]

When GT boxes are absent (approximate):
  Precision ≈ fraction of images with exactly 1 detection
  Recall    ≈ detection rate (assumes 1 GT face per image)

Usage
-----
    from pipeline.detection_pipeline import DetectionRecord
    from metrics.detection_metrics import DetectionMetrics, compute_iou

    metrics = DetectionMetrics.compute(records, iou_threshold=0.5)
    print(metrics)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

from pipeline.detection_pipeline import DetectionRecord


# ---------------------------------------------------------------------------
# IoU utility
# ---------------------------------------------------------------------------

def compute_iou(box_a: List[int], box_b: List[int]) -> float:
    """
    Compute Intersection over Union between two bounding boxes.

    Args:
        box_a: [x1, y1, x2, y2]
        box_b: [x1, y1, x2, y2]

    Returns:
        IoU in [0.0, 1.0]. Returns 0.0 for degenerate boxes.
    """
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    # Intersection
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    inter_w = max(0, ix2 - ix1)
    inter_h = max(0, iy2 - iy1)
    inter_area = inter_w * inter_h

    if inter_area == 0:
        return 0.0

    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union_area = area_a + area_b - inter_area

    if union_area <= 0:
        return 0.0

    return float(inter_area / union_area)


# ---------------------------------------------------------------------------
# DetectionMetricsResult dataclass
# ---------------------------------------------------------------------------

@dataclass
class DetectionMetricsResult:
    """
    Computed detection metrics for one detector over a set of images.

    Attributes:
        detection_rate:  Fraction of images with ≥1 face detected.
        precision:       TP / (TP + FP). None if not computable.
        recall:          TP / (TP + FN). None if not computable.
        tp:              True positive count (IoU-based, if GT available).
        fp:              False positive count.
        fn:              False negative count.
        total_images:    Total number of input images.
        detected_images: Number of images with ≥1 detection.
        gt_available:    True if ground-truth boxes were used.
        iou_threshold:   IoU threshold used for matching.
    """
    detection_rate: float
    precision: Optional[float]
    recall: Optional[float]
    tp: int
    fp: int
    fn: int
    total_images: int
    detected_images: int
    gt_available: bool
    iou_threshold: float

    def to_dict(self) -> dict:
        return {
            "detection_rate": round(self.detection_rate, 6),
            "precision": round(self.precision, 6) if self.precision is not None else None,
            "recall": round(self.recall, 6) if self.recall is not None else None,
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "total_images": self.total_images,
            "detected_images": self.detected_images,
            "gt_available": self.gt_available,
            "iou_threshold": self.iou_threshold,
        }

    def __str__(self) -> str:
        prec = f"{self.precision:.4f}" if self.precision is not None else "N/A"
        rec  = f"{self.recall:.4f}"    if self.recall  is not None else "N/A"
        return (
            f"DetectionMetrics("
            f"detection_rate={self.detection_rate:.4f}, "
            f"precision={prec}, recall={rec}, "
            f"TP={self.tp}, FP={self.fp}, FN={self.fn}, "
            f"gt={'yes' if self.gt_available else 'approx'})"
        )


# ---------------------------------------------------------------------------
# DetectionMetrics
# ---------------------------------------------------------------------------

class DetectionMetrics:
    """
    Computes detection metrics from a list of DetectionRecords.

    Supports two modes:
      1. IoU-based (when ground_truth_boxes are present in records).
      2. Approximate (when GT boxes are absent — assumes 1 face per image).
    """

    @staticmethod
    def compute(
        records: List[DetectionRecord],
        iou_threshold: float = 0.5,
    ) -> DetectionMetricsResult:
        """
        Compute detection metrics over a list of DetectionRecords.

        Args:
            records:       Output of DetectionPipeline.run().
            iou_threshold: IoU threshold for TP/FP/FN classification. Default 0.5.

        Returns:
            DetectionMetricsResult with all computed metrics.
        """
        if not records:
            return DetectionMetricsResult(
                detection_rate=0.0, precision=None, recall=None,
                tp=0, fp=0, fn=0,
                total_images=0, detected_images=0,
                gt_available=False, iou_threshold=iou_threshold,
            )

        total = len(records)
        detected_images = sum(1 for r in records if r.detected)
        detection_rate = detected_images / total

        # Check if any record has GT boxes
        has_gt = any(r.ground_truth_boxes is not None for r in records)

        if has_gt:
            tp, fp, fn = DetectionMetrics._iou_based_counts(records, iou_threshold)
            precision = tp / (tp + fp) if (tp + fp) > 0 else None
            recall    = tp / (tp + fn) if (tp + fn) > 0 else None
        else:
            # Approximate mode: single-face assumption
            # Precision ≈ fraction of images with exactly 1 detection
            single_det = sum(1 for r in records if r.face_count == 1)
            precision = single_det / total if total > 0 else None
            recall    = detection_rate  # same as detection rate under single-face assumption
            tp = single_det
            fp = sum(max(0, r.face_count - 1) for r in records)  # extra detections
            fn = total - detected_images  # missed images

        return DetectionMetricsResult(
            detection_rate=detection_rate,
            precision=precision,
            recall=recall,
            tp=tp,
            fp=fp,
            fn=fn,
            total_images=total,
            detected_images=detected_images,
            gt_available=has_gt,
            iou_threshold=iou_threshold,
        )

    @staticmethod
    def _iou_based_counts(
        records: List[DetectionRecord],
        iou_threshold: float,
    ) -> tuple:
        """
        Compute TP, FP, FN using IoU matching between detections and GT boxes.

        Matching strategy: greedy — each GT box is matched to at most one
        detected box (highest IoU first). Unmatched detections → FP.
        Unmatched GT boxes → FN.

        Returns:
            (tp, fp, fn) as integers.
        """
        tp = fp = fn = 0

        for record in records:
            gt_boxes = record.ground_truth_boxes or []
            det_boxes = [d.bbox for d in record.detections]

            if not gt_boxes and not det_boxes:
                continue
            if not gt_boxes:
                fp += len(det_boxes)
                continue
            if not det_boxes:
                fn += len(gt_boxes)
                continue

            # Build IoU matrix: rows=GT, cols=detections
            matched_gt = set()
            matched_det = set()

            # Collect all (iou, gt_idx, det_idx) pairs above threshold
            pairs = []
            for gi, gt in enumerate(gt_boxes):
                for di, det in enumerate(det_boxes):
                    iou = compute_iou(gt, det)
                    if iou >= iou_threshold:
                        pairs.append((iou, gi, di))

            # Greedy match: highest IoU first
            pairs.sort(key=lambda x: x[0], reverse=True)
            for iou_val, gi, di in pairs:
                if gi not in matched_gt and di not in matched_det:
                    matched_gt.add(gi)
                    matched_det.add(di)
                    tp += 1

            fp += len(det_boxes) - len(matched_det)
            fn += len(gt_boxes)  - len(matched_gt)

        return tp, fp, fn
