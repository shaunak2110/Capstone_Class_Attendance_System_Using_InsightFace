# Design Document: Face Recognition Evaluation Pipeline

## Overview

The evaluation pipeline is a self-contained research tool under `backend/evaluation/` that systematically benchmarks multiple face detection and recognition models on a fixed classroom dataset. It produces quantitative metrics, reproducible experiment logs, and publication-quality charts suitable for a research paper.

**Key design principles:**
- Zero coupling to the production backend — no imports cross the `backend/evaluation/` boundary.
- All behaviour is driven by a single YAML config file.
- Every experiment is reproducible via a fixed random seed.
- The pipeline is additive: new detectors or recognizers require only a new file implementing the relevant ABC.

---

## Architecture

### High-Level Component Map

```
run_experiments.py  (ExperimentRunner)
        │
        ├── utils/image_loader.py      (DatasetSplitter)
        │         └── dataset/raw/<identity>/
        │
        ├── pipeline/detection_pipeline.py   (DetectionPipeline)
        │         └── detection/<detector>.py  (BaseDetector subclass)
        │
        ├── pipeline/recognition_pipeline.py  (RecognitionPipeline)
        │         └── recognition/<recognizer>.py  (BaseRecognizer subclass)
        │
        ├── metrics/detection_metrics.py   (DetectionMetrics)
        ├── metrics/recognition_metrics.py  (RecognitionMetrics)
        │
        └── utils/visualization.py     (ReportGenerator)
                  └── results/{logs,plots,reports}/
```

### Data Flow

```
dataset/raw/<id>/
      │
      ▼
DatasetSplitter.split()
      │  seed, gallery_ratio, open_set_ratio
      ├──► GallerySet  [(identity, image_path), ...]
      └──► ProbeSet    [(identity, image_path), ...]
                │
                ▼  (for each run, for each detector×recognizer pair)
      DetectionPipeline.run(images)
                │  BGR image → BaseDetector.detect()
                ▼
      [DetectionResult(bbox, score, crop), ...]
                │
                ▼
      RecognitionPipeline.build_gallery(gallery_crops)
                │  BaseRecognizer.build_gallery()
                ▼
      RecognitionPipeline.predict(probe_crops)
                │  BaseRecognizer.predict()
                ▼
      PredictionRecord(image_path, true_label, predicted_label,
                       similarity_score, detected, detection_ms,
                       recognition_ms, total_ms)
                │
                ├──► results/logs/<det>_<rec>_predictions.csv
                │
                ▼
      DetectionMetrics.compute()  ──► detection_metrics.csv
      RecognitionMetrics.compute() ──► recognition_metrics.csv
                                       condition_metrics.csv
                                       embedding_metrics.csv
                                       timing_<det>_<rec>.csv
                │
                ▼
      ReportGenerator.generate()
                ├──► results/plots/*.png
                └──► results/reports/final_report.md
```

---

## Components and Interfaces

### BaseDetector (detection/__init__.py)

```python
from abc import ABC, abstractmethod
import numpy as np
from dataclasses import dataclass
from typing import List

@dataclass
class DetectionResult:
    bbox: List[int]          # [x1, y1, x2, y2] pixel coords
    confidence: float        # in [0.0, 1.0]
    crop: np.ndarray         # BGR face crop

class BaseDetector(ABC):
    @abstractmethod
    def detect(self, image_bgr: np.ndarray) -> List[DetectionResult]:
        """Accept a BGR image, return zero or more DetectionResult objects."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier used in filenames and logs (e.g. 'insightface')."""
        ...
```

### Concrete Detectors

| Class | File | Backend | Notes |
|---|---|---|---|
| `InsightFaceDetector` | `insightface_detector.py` | `insightface` buffalo_l `det_10g.onnx` | ONNX, CPU/GPU |
| `HaarcascadeDetector` | `haarcascade_detector.py` | `cv2.CascadeClassifier` | Ships with OpenCV |
| `RetinaFaceDetector` | `retinaface_detector.py` | `retinaface` package | Pure Python |
| `YOLODetector` | `yolo_detector.py` | `ultralytics` YOLO | Optional; skipped if model absent |

Each concrete detector:
- Raises `ImportError` / `FileNotFoundError` in `__init__` if its dependency is missing.
- Returns `[]` when no face is found.
- Does **not** perform preprocessing — that is the caller's responsibility.

### BaseRecognizer (recognition/__init__.py)

```python
from abc import ABC, abstractmethod
import numpy as np
from typing import List, Optional, Tuple

class BaseRecognizer(ABC):
    @abstractmethod
    def build_gallery(
        self,
        pairs: List[Tuple[str, np.ndarray]]  # (identity_label, face_crop)
    ) -> None:
        """Store reference embeddings / model state for all gallery identities."""
        ...

    @abstractmethod
    def predict(
        self,
        face_crop: np.ndarray,
        threshold: float,
        open_set: bool = False
    ) -> Tuple[str, float]:
        """
        Return (predicted_label, similarity_score).
        If open_set=True and best score < threshold, return ("unknown", score).
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def produces_embeddings(self) -> bool:
        """False for LBPH (no fixed-length embedding vector)."""
        return True
```

### Concrete Recognizers

| Class | File | Embedding | Distance |
|---|---|---|---|
| `InsightFaceRecognizer` | `insightface_recognizer.py` | 512-dim ArcFace (L2-norm) | Euclidean |
| `LBPHRecognizer` | `lbph_recognizer.py` | None (histogram model) | Built-in confidence |
| `DlibRecognizer` | `dlib_recognizer.py` | 128-dim `face_recognition` | Cosine |

`LBPHRecognizer.produces_embeddings` returns `False`; embedding space analysis is skipped for it.

### DatasetSplitter (utils/image_loader.py)

```python
@dataclass
class SplitResult:
    gallery: List[Tuple[str, Path]]   # (identity, image_path)
    probe:   List[Tuple[str, Path]]
    unknown_identities: List[str]     # withheld in open-set mode

class DatasetSplitter:
    def __init__(self, config: ExperimentConfig): ...

    def split(self, run_index: int = 0) -> SplitResult:
        """
        Seed = config.random_seed + run_index.
        Guarantees ≥1 image per identity in both gallery and probe.
        Withholds floor(N * open_set_ratio) identities as unknown.
        Skips identities with < 2 images (logs warning).
        """
        ...

    def preprocess(self, image_path: Path) -> np.ndarray:
        """Resize to config.image_size, ensure BGR, clip to [0,255]."""
        ...

    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp'}
```

### DetectionPipeline (pipeline/detection_pipeline.py)

```python
class DetectionPipeline:
    def __init__(self, detector: BaseDetector): ...

    def run(
        self,
        image_paths: List[Path],
        annotations: Optional[Dict[str, List[List[int]]]] = None
    ) -> List[DetectionRecord]:
        """
        For each image: preprocess → detect → record timing.
        Returns one DetectionRecord per image (empty detections included).
        """
        ...

@dataclass
class DetectionRecord:
    image_path: Path
    identity: str
    detections: List[DetectionResult]
    detection_ms: float
    ground_truth_boxes: Optional[List[List[int]]]
```

### RecognitionPipeline (pipeline/recognition_pipeline.py)

```python
class RecognitionPipeline:
    def __init__(self, recognizer: BaseRecognizer, config: ExperimentConfig): ...

    def build_gallery(self, gallery: List[Tuple[str, Path]]) -> None:
        """Load images, preprocess, call recognizer.build_gallery()."""
        ...

    def predict_probe(
        self,
        probe: List[Tuple[str, Path]],
        detection_records: List[DetectionRecord]
    ) -> List[PredictionRecord]:
        """
        For each probe image with a detected face crop:
          - call recognizer.predict()
          - record timing
        For images with no detection: detected=False, predicted_label=None.
        """
        ...

@dataclass
class PredictionRecord:
    image_path: Path
    true_label: str
    predicted_label: Optional[str]
    similarity_score: Optional[float]
    detected: bool
    detection_ms: float
    recognition_ms: float
    total_ms: float
```

### ExperimentRunner (run_experiments.py)

```python
class ExperimentRunner:
    def __init__(self, config: ExperimentConfig): ...

    def run_all(self) -> None:
        """
        For each run in range(config.num_runs):
          split = DatasetSplitter.split(run_index)
          for each (detector, recognizer) pair:
            run_single_experiment(split, detector, recognizer, run_index)
        aggregate_multi_run_stats()
        generate_report()
        """
        ...

    def run_single_experiment(
        self,
        split: SplitResult,
        detector: BaseDetector,
        recognizer: BaseRecognizer,
        run_index: int
    ) -> None: ...
```

---

## Data Models

### ExperimentConfig

```python
@dataclass
class ExperimentConfig:
    dataset_path: Path
    gallery_ratio: float          # default 0.70
    random_seed: int              # default 42
    image_size: Tuple[int, int]   # default (640, 640)
    detectors: List[str]
    recognizers: List[str]
    similarity_threshold: float   # default 0.85
    output_dir: Path              # default Path("results/")
    open_set_ratio: float         # default 0.0
    num_runs: int                 # default 1
```

Loaded via `configs/experiment_config.yaml`. Missing required keys raise `ValueError` before any experiment starts.

### Annotations and Conditions

```python
# annotations.json schema (per identity folder)
# { "img1.jpg": [[x1,y1,x2,y2], ...], ... }
AnnotationsMap = Dict[str, List[List[int]]]

# conditions.json schema (per identity folder)
# { "img1.jpg": {"lighting": "bright", "angle": "frontal"}, ... }
ConditionsMap = Dict[str, Dict[str, str]]
```

Both files are optional. Absence is handled gracefully; malformed JSON logs a warning and treats the identity as unannotated.

### Output CSV Schemas

| File | Columns |
|---|---|
| `<det>_<rec>_predictions.csv` | `image_path, true_label, predicted_label, similarity_score, detected` |
| `<det>_<rec>_run_<n>_predictions.csv` | same as above |
| `detection_metrics.csv` | `detector, detection_rate, precision, recall` |
| `recognition_metrics.csv` | `detector, recognizer, accuracy, FAR, FRR, EER_threshold, accuracy_at_EER, FAR_at_EER, FRR_at_EER, accuracy_mean, accuracy_std, FAR_mean, FAR_std, FRR_mean, FRR_std, open_set_detection_rate, false_alarm_rate` |
| `condition_metrics.csv` | `detector, recognizer, condition_type, condition_value, accuracy, FAR, FRR` |
| `embedding_metrics.csv` | `recognizer, intra_class_distance, inter_class_distance, fisher_discriminant_ratio` |
| `timing_<det>_<rec>.csv` | `image_path, detection_ms, recognition_ms, total_ms` |
| `failures/<det>_<rec>_failures.csv` | `image_path, true_label, predicted_label, similarity_score, condition` |

---

## Experiment Loop Design

### Run / Seed / Config Handling

```
num_runs = N
random_seed = S

for run_index in 0..N-1:
    effective_seed = S + run_index
    split = DatasetSplitter.split(run_index)   # uses effective_seed internally

    for (detector, recognizer) in cartesian_product(detectors, recognizers):
        try:
            run_single_experiment(split, detector, recognizer, run_index)
        except (ImportError, FileNotFoundError) as e:
            log_skip(detector, recognizer, reason=str(e))
            continue
        except Exception as e:
            log_failure(detector, recognizer, traceback=format_exc())
            mark_failed_in_summary()
            continue

aggregate_stats_across_runs()
generate_report()
```

**Key invariants:**
- Gallery is always built fresh per experiment (no cross-contamination between recognizer states).
- Seeds are deterministic: run 0 always uses `S`, run 1 uses `S+1`, etc.
- Failed experiments do not halt the runner; they are marked in the summary.

### Interactive Mode (`--interactive`)

```
if --interactive:
    dataset_path = prompt_with_retry(validate_dataset_path, max_retries=3)
    gallery_ratio = prompt("Gallery split ratio [0.70]: ")
    detectors     = prompt("Detectors to run [insightface,haarcascade,retinaface]: ")
    write_config(configs/experiment_config.yaml)
    # then proceed with normal run
```

---

## Storage Design

```
results/
├── logs/
│   ├── experiment_log.txt                    # timestamps, versions, config, stack traces
│   ├── detection_metrics.csv
│   ├── recognition_metrics.csv
│   ├── condition_metrics.csv
│   ├── embedding_metrics.csv
│   ├── timing_<det>_<rec>.csv               # one file per (det, rec) pair
│   ├── <det>_<rec>_predictions.csv          # single-run or final-run predictions
│   ├── <det>_<rec>_run_<n>_predictions.csv  # per-run predictions when num_runs > 1
│   └── failures/
│       ├── <det>_<rec>/                     # annotated failure images
│       └── <det>_<rec>_failures.csv
├── plots/
│   ├── accuracy_comparison.png
│   ├── far_frr_comparison.png
│   ├── det_curve.png
│   ├── <det>_<rec>_confusion_matrix.png
│   ├── threshold_sweep_<det>_<rec>.png
│   ├── condition_analysis_<condition_type>.png
│   └── embedding_space_<recognizer>.png
└── reports/
    └── final_report.md
```

**Naming convention:** detector and recognizer names are the `.name` property of each class (lowercase, no spaces), e.g. `insightface_insightface`, `haarcascade_lbph`.

**Failure image annotation:** OpenCV `putText` with white text on a dark semi-transparent rectangle overlay. Font scale is computed as `max(0.5, image_width / 1000)` to remain legible at any resolution.

---

## Example `configs/experiment_config.yaml`

```yaml
# Face Recognition Evaluation Pipeline — Experiment Config
# All paths are relative to backend/evaluation/

dataset_path: dataset/raw
gallery_ratio: 0.70
random_seed: 42
image_size: [640, 640]

detectors:
  - insightface
  - haarcascade
  - retinaface
  # - yolo   # uncomment if YOLO model file is present

recognizers:
  - insightface
  - lbph
  - dlib

similarity_threshold: 0.85
output_dir: results/

# Open-set evaluation (0.0 = closed-set)
open_set_ratio: 0.0

# Statistical robustness: repeat each experiment N times
num_runs: 1
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

**Property reflection:** After reviewing all testable criteria, the following consolidations were made:
- Split ratio (2.4) and minimum-partition guarantee (2.5) are combined into one comprehensive split invariant property.
- Detector interface (3.2) and recognizer interface (4.2, 4.3) are each one property covering all concrete implementations.
- Metric mathematical relationships (6.1, 7.1) are combined into one metrics invariant property.
- Timing statistics (18.2) are one property covering all five statistics.
- Multi-run seed (21.2) and reproducibility (12.2) are combined into one reproducibility property.

### Property 1: Dataset split invariants

*For any* dataset with N identities each having ≥2 images, and any gallery_ratio r ∈ (0, 1), after calling `DatasetSplitter.split()`:
- Every identity appears in both gallery and probe (≥1 image each).
- The gallery fraction for each identity is within ⌈1/count⌉ of r (rounding tolerance).
- The union of gallery and probe equals the full image set for that identity (no images lost or duplicated).

**Validates: Requirements 2.4, 2.5**

### Property 2: Split reproducibility

*For any* dataset, seed, and run_index, calling `DatasetSplitter.split(run_index)` twice with the same seed produces identical gallery and probe sets. Calling it with `run_index=i` vs `run_index=j` (i ≠ j) produces different splits.

**Validates: Requirements 2.6, 12.2, 21.2**

### Property 3: Image preprocessing invariants

*For any* input image of any size and channel format, `DatasetSplitter.preprocess()` returns an array with shape `(config.image_size[1], config.image_size[0], 3)`, dtype uint8, and all pixel values in [0, 255].

**Validates: Requirements 2.7**

### Property 4: Detector interface contract

*For any* valid BGR image passed to any concrete `BaseDetector.detect()` implementation, every returned `DetectionResult` satisfies: `bbox` is a list of 4 integers with x1 < x2 and y1 < y2, `confidence` ∈ [0.0, 1.0], and `crop` is a non-empty BGR numpy array.

**Validates: Requirements 3.2**

### Property 5: Recognizer gallery round-trip

*For any* list of (identity_label, face_crop) pairs passed to `BaseRecognizer.build_gallery()`, calling `predict()` with a gallery crop of identity X should return X as the predicted label (assuming a non-degenerate gallery with distinct identities and a reasonable threshold).

**Validates: Requirements 4.2, 4.3**

### Property 6: Experiment combinatorial coverage

*For any* list of N enabled detectors and M enabled recognizers, `ExperimentRunner.run_all()` attempts exactly N × M experiments (skipping only those where the detector or recognizer raises an import/file error).

**Validates: Requirements 5.1**

### Property 7: Predictions CSV completeness

*For any* experiment run over a probe set of K images, the resulting predictions CSV contains exactly K rows (one per probe image), each with the columns `image_path, true_label, predicted_label, similarity_score, detected`.

**Validates: Requirements 5.5**

### Property 8: Detection metrics mathematical invariants

*For any* set of detection results and ground-truth annotations, the computed metrics satisfy: `detection_rate` ∈ [0, 1], `precision` ∈ [0, 1], `recall` ∈ [0, 1], and when TP + FP > 0: `precision = TP / (TP + FP)`, and when TP + FN > 0: `recall = TP / (TP + FN)`.

**Validates: Requirements 6.1**

### Property 9: Recognition metrics mathematical invariants

*For any* set of prediction records, the computed metrics satisfy: `accuracy` ∈ [0, 1], `FAR` ∈ [0, 1], `FRR` ∈ [0, 1], and the confusion matrix rows sum to the correct per-identity probe counts.

**Validates: Requirements 7.1**

### Property 10: IoU symmetry and bounds

*For any* two bounding boxes A and B, `compute_iou(A, B)` ∈ [0, 1], `compute_iou(A, A) = 1.0`, and `compute_iou(A, B) = compute_iou(B, A)`.

**Validates: Requirements 14.2**

### Property 11: EER threshold minimises |FAR − FRR|

*For any* set of similarity scores and ground-truth match/non-match labels, the EER threshold T* computed by sweeping ≥100 evenly spaced values minimises |FAR(T) − FRR(T)| over all evaluated thresholds.

**Validates: Requirements 15.2, 15.5**

### Property 12: Open-set metrics partition

*For any* set of unknown probe predictions in open-set mode, `open_set_detection_rate + false_alarm_rate = 1.0` (every unknown probe is either correctly rejected or incorrectly accepted).

**Validates: Requirements 16.4**

### Property 13: Condition metrics consistency

*For any* set of predictions with condition labels, the per-condition prediction subsets are disjoint, their union equals the full prediction set for images that have condition annotations, and per-condition accuracy/FAR/FRR are computed using the same formulas as the global metrics.

**Validates: Requirements 17.2**

### Property 14: Timing statistics invariants

*For any* list of per-image timing values `[t1, ..., tN]` (N ≥ 1), the computed statistics satisfy: `min ≤ median ≤ mean ≤ max`, `std ≥ 0`, and `min = max` iff `std = 0`.

**Validates: Requirements 18.2**

### Property 15: Embedding space metric invariants

*For any* set of labeled gallery embeddings with ≥2 distinct identities, `intra_class_distance ≥ 0`, `inter_class_distance ≥ 0`, and `fisher_discriminant_ratio = inter_class_distance / intra_class_distance` (when intra > 0).

**Validates: Requirements 19.1**

### Property 16: Failure set correctness

*For any* set of prediction records, the failure set equals exactly the subset where `predicted_label ≠ true_label`, and the failures CSV row count equals the size of that subset.

**Validates: Requirements 20.1, 20.2**

### Property 17: Multi-run aggregation correctness

*For any* list of per-run metric values `[v1, ..., vN]`, the aggregated `mean = sum(vi)/N` and `std = sqrt(sum((vi - mean)^2) / N)` match standard statistical definitions.

**Validates: Requirements 21.4**

### Property 18: Config missing-key detection

*For any* config dict missing one or more required keys, `ExperimentConfig.from_dict()` raises `ValueError` containing the name of the missing key, and no experiment is started.

**Validates: Requirements 10.3**

---

## Error Handling

### Strategy

| Situation | Behaviour |
|---|---|
| Detector/Recognizer import fails | Log reason, skip all experiments for that model, continue |
| YOLO model file absent | Graceful skip (not an error) |
| Unhandled exception during experiment | Log full stack trace, mark experiment as `FAILED` in summary, continue |
| Config key missing | `ValueError` raised immediately, pipeline halts before any experiment |
| `annotations.json` malformed JSON | Warning logged, identity treated as unannotated |
| `conditions.json` malformed JSON | Warning logged, identity treated as unconditioned |
| Identity with < 2 images | Warning logged, identity skipped |
| Interactive mode: invalid dataset path | Re-prompt up to 3 times, then exit with descriptive error |
| No faces detected in probe image | `detected=False` recorded; counts toward FRR |

### Logging

All log output goes to `results/logs/experiment_log.txt`. Each entry is prefixed with an ISO-8601 timestamp. The log records:
- Python version and library versions at startup.
- Full config YAML contents.
- Per-experiment start/end/duration.
- Skip reasons and failure stack traces.
- Informational messages (zero failures, LBPH embedding skip, etc.).

---

## Performance Considerations

### Batching

- **Detection**: Detectors process one image at a time (the standard interface). InsightFace and RetinaFace internally batch if the underlying library supports it; the wrapper does not need to manage this.
- **Recognition**: `build_gallery` receives all gallery crops at once, allowing batch embedding extraction. InsightFaceRecognizer and DlibRecognizer should extract all embeddings in a single forward pass where the library permits.

### Embedding Caching

Gallery embeddings are computed once per experiment run and held in memory for the duration of probe prediction. They are **not** persisted to disk between runs (each run uses a fresh split, so cached embeddings would be invalid).

For multi-run experiments (`num_runs > 1`), the gallery is rebuilt for each run. This is intentional — the split changes per run.

### Image Loading

`DatasetSplitter.preprocess()` is called lazily (at the point of use), not eagerly at split time. This avoids loading the entire dataset into memory simultaneously. For large datasets, consider a generator-based approach in `DetectionPipeline.run()`.

### t-SNE

t-SNE is run once per embedding-based recognizer after all gallery embeddings are collected. For datasets with many identities, use `sklearn.manifold.TSNE` with `n_jobs=-1`. PCA is offered as a faster fallback if the identity count exceeds a configurable threshold (default 50).

### Timing Measurement

Use `time.perf_counter()` (monotonic, high-resolution). Preprocessing and image loading are excluded from `detection_ms` and `recognition_ms` measurements. The timer wraps only the `detector.detect()` and `recognizer.predict()` calls respectively.

---

## Testing Strategy

### Unit Tests

Focus on pure functions and data transformations:
- `DatasetSplitter.split()` — split ratio, minimum partition, reproducibility.
- `DatasetSplitter.preprocess()` — output shape, dtype, value range.
- `compute_iou()` — symmetry, bounds, known examples.
- `DetectionMetrics.compute()` — precision/recall formulas with synthetic data.
- `RecognitionMetrics.compute()` — accuracy/FAR/FRR formulas with synthetic data.
- `RecognitionMetrics.compute_eer()` — EER threshold minimises |FAR − FRR|.
- `RecognitionMetrics.compute_embedding_metrics()` — FDR formula.
- `RecognitionMetrics.compute_timing_stats()` — mean/std/min/max invariants.
- `ExperimentConfig.from_dict()` — missing key raises ValueError.

### Property-Based Tests

Use `hypothesis` library, minimum 100 iterations per property. Each test is tagged with the property it validates.

- **Property 1** — `@given(datasets, ratios)` → split invariants hold.
- **Property 2** — `@given(datasets, seeds, run_indices)` → same seed → same split; different index → different split.
- **Property 3** — `@given(images)` → preprocessing output shape/dtype/range.
- **Property 4** — `@given(bgr_images)` → detector output structure (using mock detectors).
- **Property 5** — `@given(identity_crop_lists)` → gallery round-trip (using InsightFaceRecognizer with mocked ONNX).
- **Property 6** — `@given(detector_lists, recognizer_lists)` → N×M experiments attempted.
- **Property 7** — `@given(probe_sets)` → predictions CSV row count = probe count.
- **Property 8** — `@given(detection_results, annotations)` → metric bounds and formulas.
- **Property 9** — `@given(prediction_records)` → metric bounds and confusion matrix sums.
- **Property 10** — `@given(bboxes_a, bboxes_b)` → IoU symmetry, bounds, self-IoU=1.
- **Property 11** — `@given(score_label_lists)` → EER threshold minimises |FAR−FRR|.
- **Property 12** — `@given(unknown_probe_predictions)` → open-set rate + false alarm = 1.
- **Property 13** — `@given(predictions_with_conditions)` → condition subsets partition full set.
- **Property 14** — `@given(timing_lists)` → min ≤ median ≤ mean ≤ max, std ≥ 0.
- **Property 15** — `@given(labeled_embeddings)` → FDR formula and non-negativity.
- **Property 16** — `@given(prediction_records)` → failure set = {p | predicted ≠ true}.
- **Property 17** — `@given(metric_value_lists)` → mean/std match standard formulas.
- **Property 18** — `@given(config_dicts_with_missing_keys)` → ValueError with key name.

### Integration Tests

Run with a small synthetic dataset (3 identities × 4 images each):
- Full pipeline end-to-end with HaarcascadeDetector + LBPHRecognizer (no heavy dependencies).
- Verify all expected output files are created.
- Verify `experiment_log.txt` contains required metadata fields.
- Verify `final_report.md` contains required section headers.

### Smoke Tests

- All detector and recognizer files exist and are importable.
- `BaseDetector` and `BaseRecognizer` are abstract (cannot be instantiated directly).
- `requirements-evaluation.txt` exists and lists all required packages.
- No file in `backend/evaluation/` imports from outside `backend/evaluation/`.
