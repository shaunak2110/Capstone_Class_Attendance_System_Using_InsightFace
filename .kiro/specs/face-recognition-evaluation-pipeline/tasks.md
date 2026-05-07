# Implementation Plan: Face Recognition Evaluation Pipeline

## Overview

Implement a self-contained research evaluation pipeline under `backend/evaluation/` that benchmarks multiple face detection and recognition models on a classroom dataset. The implementation follows the design document exactly, building from the foundation (config, dataset utilities) through detection/recognition layers, metrics, visualisation, and the experiment runner, finishing with property-based tests for all 18 correctness properties.

All code is Python. No file in `backend/evaluation/` may import from outside that directory tree.

---

## Tasks

- [x] 1. Project scaffolding and dependency files
  - Create `backend/evaluation/__init__.py` (already exists — verify it is empty or add module docstring)
  - Create `backend/evaluation/configs/__init__.py`
  - Create `backend/evaluation/dataset/__init__.py`
  - Create `backend/evaluation/detection/__init__.py` (already exists — will be replaced in Task 3)
  - Create `backend/evaluation/recognition/__init__.py`
  - Create `backend/evaluation/pipeline/__init__.py`
  - Create `backend/evaluation/metrics/__init__.py`
  - Create `backend/evaluation/utils/__init__.py`
  - Create `backend/evaluation/tests/__init__.py`
  - Write `backend/evaluation/requirements-evaluation.txt` listing all required packages with pinned major versions: `opencv-python`, `numpy`, `insightface`, `onnxruntime`, `retinaface`, `face_recognition`, `dlib`, `pyyaml`, `matplotlib`, `seaborn`, `pandas`, `scikit-learn`, `hypothesis`, `ultralytics`
  - Write `backend/evaluation/README_EVALUATION.md` with step-by-step instructions: create virtual environment, install `requirements-evaluation.txt`, place dataset under `dataset/raw/`, run `python run_experiments.py`
  - _Requirements: 1.2, 1.3, 13.1, 13.2, 13.3_

- [x] 2. Configuration system
  - [x] 2.1 Implement `ExperimentConfig` dataclass and YAML loader in `backend/evaluation/configs/config.py`
    - Define `ExperimentConfig` dataclass with all fields: `dataset_path`, `gallery_ratio`, `random_seed`, `image_size`, `detectors`, `recognizers`, `similarity_threshold`, `output_dir`, `open_set_ratio`, `num_runs`
    - Implement `ExperimentConfig.from_dict(d)` classmethod that raises `ValueError` naming any missing required key
    - Implement `ExperimentConfig.from_yaml(path)` that reads the YAML file and calls `from_dict`
    - Apply defaults: `gallery_ratio=0.70`, `random_seed=42`, `image_size=(640,640)`, `similarity_threshold=0.85`, `output_dir=Path("results/")`, `open_set_ratio=0.0`, `num_runs=1`
    - _Requirements: 10.1, 10.2, 10.3, 16.1, 21.1_

  - [ ]* 2.2 Write property test for config missing-key detection
    - **Property 18: Config missing-key detection**
    - For any config dict missing one or more required keys, `from_dict()` raises `ValueError` containing the missing key name
    - **Validates: Requirements 10.3**

  - [x] 2.3 Write `backend/evaluation/configs/experiment_config.yaml` with all default values
    - Include all parameters from the design document example
    - Comment out `yolo` detector entry
    - _Requirements: 10.1, 10.2_

- [x] 3. Dataset utilities — `DatasetSplitter`
  - [x] 3.1 Implement `DatasetSplitter` in `backend/evaluation/utils/image_loader.py`
    - Define `SplitResult` dataclass with `gallery`, `probe`, `unknown_identities` fields
    - Implement `DatasetSplitter.__init__(config: ExperimentConfig)`
    - Implement `split(run_index=0)`: discover sub-folders under `dataset/raw/`, filter by `SUPPORTED_EXTENSIONS`, skip identities with < 2 images (log warning), shuffle with seed `config.random_seed + run_index`, apply `gallery_ratio` split guaranteeing ≥1 image per partition, withhold `floor(N * open_set_ratio)` identities as unknown
    - Implement `preprocess(image_path)`: load BGR, resize to `config.image_size`, clip to [0, 255], return uint8 ndarray
    - Load `annotations.json` and `conditions.json` per identity folder; handle missing files gracefully; log warning on malformed JSON
    - `SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp'}` (case-insensitive)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 14.1, 14.4, 14.5, 17.1_

  - [ ]* 3.2 Write property test for dataset split invariants
    - **Property 1: Dataset split invariants**
    - For any dataset with N identities each having ≥2 images and any `gallery_ratio` ∈ (0,1), every identity appears in both gallery and probe, gallery fraction is within rounding tolerance of ratio, union equals full image set
    - **Validates: Requirements 2.4, 2.5**

  - [ ]* 3.3 Write property test for split reproducibility
    - **Property 2: Split reproducibility**
    - Same seed + run_index → identical split; different run_index → different split
    - **Validates: Requirements 2.6, 12.2, 21.2**

  - [ ]* 3.4 Write property test for image preprocessing invariants
    - **Property 3: Image preprocessing invariants**
    - For any input image of any size/channel format, `preprocess()` returns shape `(H, W, 3)`, dtype uint8, all values in [0, 255]
    - **Validates: Requirements 2.7**

- [-] 4. Detection layer — `BaseDetector` and concrete detectors
  - [x] 4.1 Implement `BaseDetector` ABC and `DetectionResult` dataclass in `backend/evaluation/detection/__init__.py`
    - Define `DetectionResult` dataclass: `bbox: List[int]`, `confidence: float`, `crop: np.ndarray`
    - Define `BaseDetector` ABC with abstract methods `detect(image_bgr)` and abstract property `name`
    - _Requirements: 3.2, 3.5_

  - [x] 4.2 Implement `InsightFaceDetector` in `backend/evaluation/detection/insightface_detector.py`
    - Use InsightFace buffalo_l `det_10g.onnx` (path relative to `backend/evaluation/`)
    - Raise `FileNotFoundError` with descriptive message if model file absent
    - Return `[]` when no face detected
    - `name` property returns `"insightface"`
    - _Requirements: 3.1, 3.3, 3.4_

  - [x] 4.3 Implement `HaarcascadeDetector` in `backend/evaluation/detection/haarcascade_detector.py`
    - Use `cv2.CascadeClassifier` with `haarcascade_frontalface_default.xml`
    - Raise `FileNotFoundError` if cascade file not found
    - Return `[]` when no face detected
    - `name` property returns `"haarcascade"`
    - _Requirements: 3.1, 3.3, 3.4_

  - [ ] 4.4 Implement `RetinaFaceDetector` in `backend/evaluation/detection/retinaface_detector.py`
    - Use `retinaface` Python package
    - Raise `ImportError` with descriptive message if package not installed
    - Return `[]` when no face detected
    - `name` property returns `"retinaface"`
    - _Requirements: 3.1, 3.3, 3.4_

  - [ ] 4.5 Implement `YOLODetector` in `backend/evaluation/detection/yolo_detector.py`
    - Use `ultralytics` YOLO; raise `FileNotFoundError` gracefully if model file absent (not an error — runner skips it)
    - Return `[]` when no face detected
    - `name` property returns `"yolo"`
    - _Requirements: 3.1, 3.3, 3.4_

  - [ ]* 4.6 Write property test for detector interface contract
    - **Property 4: Detector interface contract**
    - For any valid BGR image, every `DetectionResult` from any concrete detector has `bbox` as 4 ints with x1 < x2 and y1 < y2, `confidence` ∈ [0.0, 1.0], `crop` is non-empty BGR ndarray
    - Use mock/stub detectors to avoid heavy dependencies in tests
    - **Validates: Requirements 3.2**

- [-] 5. Recognition layer — `BaseRecognizer` and concrete recognizers
  - [x] 5.1 Implement `BaseRecognizer` ABC in `backend/evaluation/recognition/__init__.py`
    - Define `BaseRecognizer` ABC with abstract methods `build_gallery(pairs)`, `predict(face_crop, threshold, open_set=False)`, abstract property `name`
    - Add `produces_embeddings` property defaulting to `True`
    - _Requirements: 4.2, 4.3, 4.5_

  - [x] 5.2 Implement `InsightFaceRecognizer` in `backend/evaluation/recognition/insightface_recognizer.py`
    - Generate 512-dim ArcFace embeddings using `w600k_r50.onnx`
    - L2-normalise embeddings; use Euclidean distance for matching
    - `build_gallery`: extract all embeddings in batch where possible
    - `predict`: return `("unknown", score)` when `open_set=True` and best score < threshold
    - `name` returns `"insightface"`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 5.3 Implement `LBPHRecognizer` in `backend/evaluation/recognition/lbph_recognizer.py`
    - Use `cv2.face.LBPHFaceRecognizer_create()`
    - `produces_embeddings` returns `False`
    - `predict`: return `("unknown", score)` in open-set mode when confidence exceeds threshold
    - `name` returns `"lbph"`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ] 5.4 Implement `DlibRecognizer` in `backend/evaluation/recognition/dlib_recognizer.py`
    - Use `face_recognition` library (dlib backend) for 128-dim embeddings
    - Use cosine similarity for matching
    - `predict`: return `("unknown", score)` when `open_set=True` and best score < threshold
    - `name` returns `"dlib"`
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 5.5 Write property test for recognizer gallery round-trip
    - **Property 5: Recognizer gallery round-trip**
    - For any list of (identity_label, face_crop) pairs, calling `predict()` with a gallery crop of identity X returns X as predicted label (non-degenerate gallery, reasonable threshold)
    - Use mocked ONNX/model calls to avoid heavy dependencies
    - **Validates: Requirements 4.2, 4.3**

- [x] 6. Pipeline layer — `DetectionPipeline` and `RecognitionPipeline`
  - [x] 6.1 Implement `DetectionPipeline` in `backend/evaluation/pipeline/detection_pipeline.py`
    - Define `DetectionRecord` dataclass: `image_path`, `identity`, `detections`, `detection_ms`, `ground_truth_boxes`
    - Implement `DetectionPipeline.__init__(detector: BaseDetector)`
    - Implement `run(image_paths, annotations=None)`: for each image, preprocess → detect → record timing using `time.perf_counter()`; preprocessing and loading time excluded from `detection_ms`
    - Return one `DetectionRecord` per image (empty detections included)
    - _Requirements: 5.2a, 18.1, 18.5_

  - [x] 6.2 Implement `RecognitionPipeline` in `backend/evaluation/pipeline/recognition_pipeline.py`
    - Define `PredictionRecord` dataclass: `image_path`, `true_label`, `predicted_label`, `similarity_score`, `detected`, `detection_ms`, `recognition_ms`, `total_ms`
    - Implement `RecognitionPipeline.__init__(recognizer, config)`
    - Implement `build_gallery(gallery)`: load + preprocess images, call `recognizer.build_gallery()`
    - Implement `predict_probe(probe, detection_records)`: for each probe image with detected face crop, call `recognizer.predict()` and record timing; for images with no detection, set `detected=False`, `predicted_label=None`
    - _Requirements: 5.2b, 5.2c, 5.3, 5.4, 18.1, 18.5_

- [ ] 7. Checkpoint — wire detection and recognition pipelines
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Metrics — detection metrics
  - [x] 8.1 Implement `DetectionMetrics` in `backend/evaluation/metrics/detection_metrics.py`
    - Implement `compute_iou(box_a, box_b)` standalone function: returns float in [0,1], symmetric, `iou(A,A)=1.0`
    - Implement `DetectionMetrics.compute(detection_records, annotations_map)`:
      - When annotations present: compute IoU-based precision and recall (IoU threshold ≥ 0.5)
      - When annotations absent: approximate detection rate = fraction of images with exactly one detection
      - Compute `detection_rate` = fraction of images with ≥1 detection
    - Write results to `results/logs/detection_metrics.csv` with columns `detector`, `detection_rate`, `precision`, `recall`
    - _Requirements: 6.1, 6.2, 6.3, 14.2_

  - [ ]* 8.2 Write property test for detection metrics mathematical invariants
    - **Property 8: Detection metrics mathematical invariants**
    - For any detection results and ground-truth annotations: `detection_rate` ∈ [0,1], `precision` ∈ [0,1], `recall` ∈ [0,1], precision = TP/(TP+FP) when TP+FP > 0, recall = TP/(TP+FN) when TP+FN > 0
    - **Validates: Requirements 6.1**

  - [ ]* 8.3 Write property test for IoU symmetry and bounds
    - **Property 10: IoU symmetry and bounds**
    - For any two bounding boxes A and B: `iou(A,B)` ∈ [0,1], `iou(A,A) = 1.0`, `iou(A,B) = iou(B,A)`
    - **Validates: Requirements 14.2**

- [ ] 9. Metrics — recognition metrics
  - [x] 9.1 Implement `RecognitionMetrics` in `backend/evaluation/metrics/recognition_metrics.py`
    - Implement `compute(prediction_records, config)`:
      - Accuracy (excluding no-detection images), FAR, FRR, confusion matrix
      - EER threshold sweep over ≥100 evenly spaced values; report `EER_threshold`, `accuracy_at_EER`, `FAR_at_EER`, `FRR_at_EER`
      - Open-set metrics (`open_set_detection_rate`, `false_alarm_rate`) when `open_set_ratio > 0`
      - Multi-run aggregation: `accuracy_mean`, `accuracy_std`, `FAR_mean`, `FAR_std`, `FRR_mean`, `FRR_std`
    - Implement `compute_condition_metrics(prediction_records, conditions_map)`: group by condition type/value, compute accuracy/FAR/FRR per group; write to `condition_metrics.csv`
    - Implement `compute_embedding_metrics(labeled_embeddings, recognizer_name, distance_metric)`: intra-class distance, inter-class distance, FDR; write to `embedding_metrics.csv`; skip for LBPH
    - Implement `compute_timing_stats(timing_records)`: mean, median, std, min, max for detection_ms, recognition_ms, total_ms; write to `timing_<det>_<rec>.csv`
    - Save confusion matrix PNG to `results/plots/<det>_<rec>_confusion_matrix.png`
    - Write recognition metrics to `results/logs/recognition_metrics.csv`
    - _Requirements: 7.1, 7.2, 7.3, 15.1, 15.2, 15.3, 15.5, 16.4, 16.5, 17.2, 17.3, 17.5, 18.2, 18.3, 19.1, 19.2, 19.4, 19.5, 21.4_

  - [ ]* 9.2 Write property test for recognition metrics mathematical invariants
    - **Property 9: Recognition metrics mathematical invariants**
    - For any prediction records: `accuracy` ∈ [0,1], `FAR` ∈ [0,1], `FRR` ∈ [0,1], confusion matrix rows sum to correct per-identity probe counts
    - **Validates: Requirements 7.1**

  - [ ]* 9.3 Write property test for EER threshold minimises |FAR − FRR|
    - **Property 11: EER threshold minimises |FAR − FRR|**
    - For any set of similarity scores and ground-truth match/non-match labels, the EER threshold T* computed by sweeping ≥100 values minimises |FAR(T) − FRR(T)| over all evaluated thresholds
    - **Validates: Requirements 15.2, 15.5**

  - [ ]* 9.4 Write property test for open-set metrics partition
    - **Property 12: Open-set metrics partition**
    - For any set of unknown probe predictions in open-set mode: `open_set_detection_rate + false_alarm_rate = 1.0`
    - **Validates: Requirements 16.4**

  - [ ]* 9.5 Write property test for condition metrics consistency
    - **Property 13: Condition metrics consistency**
    - Per-condition prediction subsets are disjoint, their union equals the full annotated prediction set, and per-condition accuracy/FAR/FRR use the same formulas as global metrics
    - **Validates: Requirements 17.2**

  - [ ]* 9.6 Write property test for timing statistics invariants
    - **Property 14: Timing statistics invariants**
    - For any list of per-image timing values [t1,...,tN] (N ≥ 1): `min ≤ median ≤ mean ≤ max`, `std ≥ 0`, `min = max` iff `std = 0`
    - **Validates: Requirements 18.2**

  - [ ]* 9.7 Write property test for embedding space metric invariants
    - **Property 15: Embedding space metric invariants**
    - For any labeled gallery embeddings with ≥2 distinct identities: `intra_class_distance ≥ 0`, `inter_class_distance ≥ 0`, `FDR = inter / intra` when intra > 0
    - **Validates: Requirements 19.1**

  - [ ]* 9.8 Write property test for multi-run aggregation correctness
    - **Property 17: Multi-run aggregation correctness**
    - For any list of per-run metric values [v1,...,vN]: `mean = sum(vi)/N` and `std = sqrt(sum((vi-mean)^2)/N)` match standard statistical definitions
    - **Validates: Requirements 21.4**

- [ ] 10. Checkpoint — verify metrics layer
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Visualisation — `ReportGenerator`
  - [ ] 11.1 Implement `ReportGenerator` in `backend/evaluation/utils/visualization.py`
    - Implement `plot_accuracy_comparison(metrics_df)`: bar chart of per-experiment accuracy → `results/plots/accuracy_comparison.png` at ≥150 DPI
    - Implement `plot_far_frr_comparison(metrics_df)`: grouped bar chart of FAR and FRR → `results/plots/far_frr_comparison.png` at ≥150 DPI
    - Implement `plot_det_curve(prediction_records_by_recognizer)`: FAR vs FRR curve per recognizer → `results/plots/det_curve.png` at ≥150 DPI
    - Implement `plot_threshold_sweep(prediction_records, det_name, rec_name)`: FAR and FRR vs threshold → `results/plots/threshold_sweep_<det>_<rec>.png` at ≥150 DPI
    - Implement `plot_condition_analysis(condition_metrics_df, condition_type)`: accuracy by condition value → `results/plots/condition_analysis_<condition_type>.png` at ≥150 DPI
    - Implement `plot_embedding_space(labeled_embeddings, recognizer_name)`: t-SNE (or PCA fallback when identities > 50) 2D scatter coloured by identity → `results/plots/embedding_space_<recognizer>.png` at ≥150 DPI
    - All charts: consistent colour scheme, labelled axes, titles, legend entries
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 15.4, 17.4, 19.3_

- [ ] 12. Failure case logging
  - [ ] 12.1 Implement failure case logging in `backend/evaluation/utils/failure_logger.py`
    - Implement `save_failure_images(prediction_records, det_name, rec_name, conditions_map)`:
      - Identify all records where `predicted_label ≠ true_label`
      - Annotate each image with true label, predicted label, similarity score using `cv2.putText`; font scale = `max(0.5, image_width / 1000)`; white text on dark semi-transparent rectangle overlay
      - Save to `results/logs/failures/<det>_<rec>/`
    - Implement `write_failures_csv(prediction_records, det_name, rec_name, conditions_map)`:
      - Write `results/logs/failures/<det>_<rec>_failures.csv` with columns `image_path`, `true_label`, `predicted_label`, `similarity_score`, `condition`
      - If no failures, write header-only CSV and log informational message
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5_

  - [ ]* 12.2 Write property test for failure set correctness
    - **Property 16: Failure set correctness**
    - For any prediction records, the failure set equals exactly `{p | predicted_label ≠ true_label}` and the failures CSV row count equals the size of that subset
    - **Validates: Requirements 20.1, 20.2**

- [ ] 13. Report generation — `final_report.md`
  - [ ] 13.1 Implement `generate_report(config, all_metrics, timing_stats)` in `ReportGenerator`
    - Write `results/reports/final_report.md` with sections:
      - **Dataset Description**: identities count, total images, gallery/probe ratio, image preprocessing parameters
      - **Model Comparison Table**: Markdown table `Detector | Recognizer | Accuracy | FAR | FRR` sorted by Accuracy descending; include mean ± std and 95% CI when `num_runs > 1`
      - **Timing Summary Table**: `Detector | Recognizer | Mean Detection (ms) | Mean Recognition (ms) | Mean Total (ms) | Std Total (ms)`
      - **Observations**: auto-generated bullet points (highest accuracy, lowest FAR, lowest FRR)
      - **Conclusion**: paragraph naming best-performing combination and summarising its metrics
    - Embed relative links to all generated plot images
    - _Requirements: 9.1, 9.2, 9.3, 18.4, 21.5_

- [ ] 14. Experiment runner — `ExperimentRunner`
  - [x] 14.1 Implement `ExperimentRunner` in `backend/evaluation/run_experiments.py`
    - Implement `__init__(config)`: set NumPy and Python random seeds from config
    - Implement `run_all()`: outer loop over `range(config.num_runs)`, inner loop over cartesian product of enabled detectors × recognizers; call `run_single_experiment()`; on `ImportError`/`FileNotFoundError` log skip and continue; on any other exception log full stack trace, mark experiment FAILED, continue; after all runs call `aggregate_multi_run_stats()` and `generate_report()`
    - Implement `run_single_experiment(split, detector, recognizer, run_index)`:
      - Build gallery fresh (no cross-contamination)
      - Run `DetectionPipeline.run()` over probe images
      - Run `RecognitionPipeline.predict_probe()`
      - Write per-run predictions CSV (`<det>_<rec>_run_<n>_predictions.csv` when `num_runs > 1`, else `<det>_<rec>_predictions.csv`)
      - Log start time, end time, wall-clock duration to `experiment_log.txt`
      - Call failure logger
      - Collect timing records
    - Implement `aggregate_multi_run_stats()`: compute mean/std across runs for accuracy, FAR, FRR
    - Log Python version and library versions at startup; log full config YAML contents
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 12.1, 12.2, 12.3, 21.2, 21.3, 21.6_

  - [ ]* 14.2 Write property test for experiment combinatorial coverage
    - **Property 6: Experiment combinatorial coverage**
    - For any list of N enabled detectors and M enabled recognizers, `run_all()` attempts exactly N × M experiments (skipping only those raising import/file errors)
    - **Validates: Requirements 5.1**

  - [ ]* 14.3 Write property test for predictions CSV completeness
    - **Property 7: Predictions CSV completeness**
    - For any experiment run over a probe set of K images, the predictions CSV contains exactly K rows with columns `image_path`, `true_label`, `predicted_label`, `similarity_score`, `detected`
    - **Validates: Requirements 5.5**

- [ ] 15. Interactive mode
  - [ ] 15.1 Implement `--interactive` flag handling in `run_experiments.py`
    - Parse `--interactive` CLI argument using `argparse`
    - When flag present: prompt for dataset path (validate existence + ≥1 identity sub-folder, re-prompt up to 3 times then exit with descriptive error), gallery split ratio, and list of models to run
    - Write resulting config to `configs/experiment_config.yaml` before starting experiments
    - _Requirements: 11.1, 11.2, 11.3_

- [ ] 16. Checkpoint — full pipeline integration
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 17. Integration and smoke tests
  - [ ] 17.1 Write integration test in `backend/evaluation/tests/test_integration.py`
    - Use a small synthetic dataset (3 identities × 4 images each, generated with numpy)
    - Run full pipeline end-to-end with `HaarcascadeDetector` + `LBPHRecognizer` (no heavy dependencies)
    - Assert all expected output files are created: `detection_metrics.csv`, `recognition_metrics.csv`, `<det>_<rec>_predictions.csv`, `experiment_log.txt`, `final_report.md`, `accuracy_comparison.png`
    - Assert `experiment_log.txt` contains required metadata fields (timestamp, Python version, config YAML)
    - Assert `final_report.md` contains required section headers
    - _Requirements: 1.1, 5.5, 5.6, 9.1, 9.2, 12.1_

  - [ ]* 17.2 Write smoke tests in `backend/evaluation/tests/test_smoke.py`
    - Assert all detector and recognizer files exist and are importable
    - Assert `BaseDetector` and `BaseRecognizer` cannot be instantiated directly (raise `TypeError`)
    - Assert `requirements-evaluation.txt` exists and lists all required packages
    - Assert no file in `backend/evaluation/` imports from outside `backend/evaluation/` (static import scan)
    - _Requirements: 1.1, 1.2, 3.5, 4.5_

- [ ] 18. Final checkpoint — ensure all tests pass
  - Run `python -m pytest backend/evaluation/tests/ -v` from the workspace root
  - Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use the `hypothesis` library with a minimum of 100 iterations per property
- Heavy model dependencies (InsightFace, dlib, YOLO) are mocked in property tests to avoid requiring model files during testing
- Checkpoints at Tasks 7, 10, 16, and 18 ensure incremental validation at each major layer boundary
- The `LBPHRecognizer` skips embedding space analysis (`produces_embeddings = False`); this is logged as an informational message, not an error
- All timing measurements use `time.perf_counter()` and exclude image loading/preprocessing
- t-SNE is used for embedding visualisation; PCA is the fallback when identity count > 50
