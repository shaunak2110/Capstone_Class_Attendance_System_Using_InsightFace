# Requirements Document

## Introduction

This feature introduces a research-grade, standalone evaluation pipeline located under
`backend/evaluation/`. Its purpose is to systematically compare multiple pretrained face
detection and recognition models on a fixed classroom dataset (~300 images per student,
mixed lighting, angles, and real-world conditions). The pipeline must produce quantitative
metrics, reproducible experiment logs, and output suitable for inclusion in a research paper.

The pipeline is completely independent of the existing production backend. It MUST NOT
import from or modify any file outside `backend/evaluation/`. It ships with its own
dependency file (`requirements-evaluation.txt`) and its own model wrappers that mirror —
but do not reuse — the production `InsightFaceEngine`.

---

## Glossary

- **Pipeline**: The `backend/evaluation/` module as a whole.
- **Dataset**: The collection of per-identity image folders placed under
  `backend/evaluation/dataset/raw/`. Each sub-folder is named with an identity label
  (e.g., a student PRN or a name slug).
- **Identity**: A single person represented by one sub-folder in the Dataset.
- **Gallery Set**: The subset of images per Identity used to build reference embeddings
  (training split).
- **Probe Set**: The subset of images per Identity used to test recognition (test split).
- **Detector**: A face detection model wrapper that accepts a BGR image and returns
  bounding boxes, confidence scores, and cropped face images.
- **Recognizer**: A face recognition model wrapper that generates embeddings for a face
  crop, stores Gallery embeddings, and matches Probe embeddings against the Gallery.
- **Embedding**: A fixed-length numerical vector representing a face, used for similarity
  matching.
- **Experiment**: One complete run of a single (Detector, Recognizer) combination over
  the full Dataset.
- **Run**: Synonym for Experiment in the context of `run_experiments.py`.
- **FAR**: False Acceptance Rate — the fraction of impostor pairs incorrectly accepted.
- **FRR**: False Rejection Rate — the fraction of genuine pairs incorrectly rejected.
- **IoU**: Intersection over Union — overlap metric for bounding box evaluation.
- **Experiment_Runner**: The top-level orchestrator implemented in `run_experiments.py`.
- **Dataset_Splitter**: The component in `utils/image_loader.py` responsible for
  gallery/probe splitting.
- **Detection_Pipeline**: The component in `pipeline/detection_pipeline.py` that runs a
  Detector over a set of images.
- **Recognition_Pipeline**: The component in `pipeline/recognition_pipeline.py` that
  runs a Recognizer over detected face crops.
- **Metrics_Engine**: The components in `metrics/detection_metrics.py` and
  `metrics/recognition_metrics.py` that compute evaluation metrics.
- **Report_Generator**: The component in `utils/visualization.py` and the report
  generation logic in `run_experiments.py` that produces charts and the final Markdown
  report.
- **Config**: The YAML file at `configs/experiment_config.yaml` that controls all
  tunable parameters.

---

## Requirements

---

### Requirement 1: Isolated Module Boundary

**User Story:** As a researcher, I want the evaluation pipeline to be completely
independent of the production backend, so that running experiments never risks breaking
the live attendance system.

#### Acceptance Criteria

1. THE Pipeline SHALL NOT import any module from outside the `backend/evaluation/`
   directory tree.
2. THE Pipeline SHALL declare all its Python dependencies in a dedicated
   `backend/evaluation/requirements-evaluation.txt` file, separate from
   `backend/requirements.txt`.
3. WHEN the Pipeline is executed, THE Experiment_Runner SHALL be launchable by running
   `python run_experiments.py` from within `backend/evaluation/` without modifying any
   file outside that directory.

---

### Requirement 2: Dataset Ingestion

**User Story:** As a researcher, I want the pipeline to automatically ingest a raw image
dataset organised by identity, so that I do not have to manually prepare input files.

#### Acceptance Criteria

1. WHEN the Dataset directory is provided, THE Dataset_Splitter SHALL discover all
   sub-folders under `dataset/raw/` and treat each sub-folder name as an Identity label.
2. THE Dataset_Splitter SHALL support image files with extensions `.jpg`, `.jpeg`, `.png`,
   and `.bmp` (case-insensitive).
3. IF an Identity sub-folder contains fewer than 2 images, THEN THE Dataset_Splitter
   SHALL skip that Identity and log a warning identifying the skipped folder.
4. THE Dataset_Splitter SHALL apply a configurable split ratio (gallery fraction) read
   from the Config, with a default value of 0.70 (70 % gallery, 30 % probe).
5. WHEN splitting, THE Dataset_Splitter SHALL ensure every Identity appears in both the
   Gallery Set and the Probe Set by guaranteeing at least 1 image in each partition.
6. THE Dataset_Splitter SHALL shuffle images with a fixed random seed (read from Config)
   before splitting, so that splits are reproducible across runs.
7. THE Dataset_Splitter SHALL apply standard preprocessing to every image before it is
   passed to any Detector or Recognizer: resize to the dimensions specified in Config
   (default 640 × 640), convert to BGR colour space, and clip pixel values to [0, 255].

---

### Requirement 3: Modular Detector Interface

**User Story:** As a researcher, I want each detection model to expose a uniform
interface, so that I can swap detectors without changing pipeline code.

#### Acceptance Criteria

1. THE Pipeline SHALL implement the following Detector wrappers, each in its own file
   under `detection/`:
   - `insightface_detector.py` — uses InsightFace buffalo_l detector (det_10g.onnx).
   - `haarcascade_detector.py` — uses OpenCV Haar Cascade
     (`haarcascade_frontalface_default.xml`).
   - `retinaface_detector.py` — uses the `retinaface` Python package.
   - `yolo_detector.py` — uses a YOLO-based face detection model (optional; skipped
     gracefully if the model file is absent).
2. WHEN a Detector is called with a BGR image, THE Detector SHALL return a list of
   detection results, where each result contains: a bounding box as `[x1, y1, x2, y2]`
   in pixel coordinates, a confidence score as a float in [0, 1], and a cropped face
   image as a BGR numpy array.
3. IF a Detector's required library or model file is not installed, THEN THE Detector
   SHALL raise an `ImportError` or `FileNotFoundError` with a descriptive message, and
   THE Experiment_Runner SHALL skip all Experiments involving that Detector and log the
   reason.
4. IF no face is detected in an image, THEN THE Detector SHALL return an empty list for
   that image.
5. THE Pipeline SHALL define a `BaseDetector` abstract class in
   `detection/__init__.py` that all Detector wrappers inherit from, enforcing the
   interface described in criterion 2.

---

### Requirement 4: Modular Recognizer Interface

**User Story:** As a researcher, I want each recognition model to expose a uniform
interface, so that I can swap recognizers without changing pipeline code.

#### Acceptance Criteria

1. THE Pipeline SHALL implement the following Recognizer wrappers, each in its own file
   under `recognition/`:
   - `insightface_recognizer.py` — generates 512-dim ArcFace embeddings using
     InsightFace buffalo_l (w600k_r50.onnx); uses L2-normalised Euclidean distance for
     matching.
   - `lbph_recognizer.py` — uses OpenCV `LBPHFaceRecognizer`; uses the recognizer's
     built-in confidence score for matching.
   - `dlib_recognizer.py` — generates 128-dim embeddings using the `face_recognition`
     library (dlib backend); uses cosine similarity for matching.
2. WHEN a Recognizer's `build_gallery` method is called with a list of (identity_label,
   face_crop) pairs, THE Recognizer SHALL store reference embeddings or model state for
   all provided identities.
3. WHEN a Recognizer's `predict` method is called with a single face crop, THE
   Recognizer SHALL return the predicted identity label and a similarity or confidence
   score.
4. IF a Recognizer's required library is not installed, THEN THE Recognizer SHALL raise
   an `ImportError` with a descriptive message, and THE Experiment_Runner SHALL skip all
   Experiments involving that Recognizer and log the reason.
5. THE Pipeline SHALL define a `BaseRecognizer` abstract class in
   `recognition/__init__.py` that all Recognizer wrappers inherit from, enforcing the
   interface described in criteria 2 and 3.

---

### Requirement 5: Experiment Execution

**User Story:** As a researcher, I want the pipeline to automatically run every
(Detector, Recognizer) combination and record predictions, so that I get a complete
comparison matrix without manual intervention.

#### Acceptance Criteria

1. WHEN `run_experiments.py` is executed, THE Experiment_Runner SHALL iterate over all
   enabled (Detector, Recognizer) combinations specified in the Config.
2. FOR EACH Experiment, THE Experiment_Runner SHALL:
   a. Run the Detector over every Probe image.
   b. Pass each detected face crop to the Recognizer's `predict` method.
   c. Record the predicted identity label, the true identity label, and the similarity
      score for every Probe image.
3. THE Experiment_Runner SHALL build the Gallery (call `build_gallery`) using Gallery Set
   images before running any Probe predictions for that Experiment.
4. IF a Probe image yields no detected face, THE Experiment_Runner SHALL record it as a
   missed detection and count it toward the False Rejection Rate.
5. THE Experiment_Runner SHALL write a per-Experiment CSV file to
   `results/logs/<detector>_<recognizer>_predictions.csv` containing columns:
   `image_path`, `true_label`, `predicted_label`, `similarity_score`, `detected` (bool).
6. THE Experiment_Runner SHALL log the start time, end time, and wall-clock duration of
   each Experiment to `results/logs/experiment_log.txt`.

---

### Requirement 6: Detection Metrics

**User Story:** As a researcher, I want quantitative detection metrics for each detector,
so that I can compare their reliability on classroom images.

#### Acceptance Criteria

1. THE Metrics_Engine SHALL compute the following detection metrics per Detector:
   - **Detection Rate**: fraction of images in which at least one face was detected.
   - **Precision**: fraction of detected bounding boxes that overlap a ground-truth box
     with IoU ≥ 0.5 (when ground-truth annotations are available).
   - **Recall**: fraction of ground-truth faces that were detected with IoU ≥ 0.5 (when
     ground-truth annotations are available).
2. WHERE ground-truth bounding box annotations are not available, THE Metrics_Engine
   SHALL compute an approximate detection rate using the fraction of images that yield
   exactly one detected face (single-face images are assumed to contain one ground-truth
   face).
3. THE Metrics_Engine SHALL write detection metric results to
   `results/logs/detection_metrics.csv` with columns: `detector`, `detection_rate`,
   `precision`, `recall`.

---

### Requirement 7: Recognition Metrics

**User Story:** As a researcher, I want quantitative recognition metrics for each
(Detector, Recognizer) combination, so that I can identify the best-performing pipeline
for the attendance use case.

#### Acceptance Criteria

1. THE Metrics_Engine SHALL compute the following recognition metrics per Experiment:
   - **Accuracy**: fraction of Probe images correctly identified (predicted label equals
     true label), excluding images with no detected face.
   - **FAR**: fraction of impostor probe attempts (true label ≠ gallery identity) that
     are incorrectly accepted.
   - **FRR**: fraction of genuine probe attempts (true label = gallery identity) that are
     incorrectly rejected (including missed detections).
   - **Confusion Matrix**: N × N matrix of predicted vs. true identity labels for all N
     identities in the Dataset.
2. THE Metrics_Engine SHALL write per-Experiment recognition metrics to
   `results/logs/recognition_metrics.csv` with columns: `detector`, `recognizer`,
   `accuracy`, `FAR`, `FRR`.
3. THE Metrics_Engine SHALL save the confusion matrix for each Experiment as a PNG image
   to `results/plots/<detector>_<recognizer>_confusion_matrix.png`.

---

### Requirement 8: Visualisation

**User Story:** As a researcher, I want publication-quality charts comparing all models,
so that I can include them directly in a research paper.

#### Acceptance Criteria

1. THE Report_Generator SHALL produce a bar chart comparing per-Experiment accuracy
   across all (Detector, Recognizer) combinations and save it to
   `results/plots/accuracy_comparison.png`.
2. THE Report_Generator SHALL produce a grouped bar chart comparing FAR and FRR for all
   Experiments and save it to `results/plots/far_frr_comparison.png`.
3. THE Report_Generator SHALL produce a FAR vs. FRR curve (DET curve) for each
   Recognizer (aggregated across detectors) and save it to
   `results/plots/det_curve.png`.
4. WHEN generating charts, THE Report_Generator SHALL use a consistent colour scheme and
   label all axes, titles, and legend entries clearly.
5. THE Report_Generator SHALL save all plots at a minimum resolution of 150 DPI.

---

### Requirement 9: Structured Report Generation

**User Story:** As a researcher, I want an automatically generated Markdown report
summarising all results, so that I have a ready-to-use draft for the paper's results
section.

#### Acceptance Criteria

1. WHEN all Experiments have completed, THE Report_Generator SHALL write a structured
   Markdown report to `results/reports/final_report.md`.
2. THE Report_Generator SHALL include the following sections in the report:
   - **Dataset Description**: number of identities, total images, gallery/probe split
     ratio, and image preprocessing parameters.
   - **Model Comparison Table**: a Markdown table with columns `Detector`, `Recognizer`,
     `Accuracy`, `FAR`, `FRR`, sorted by Accuracy descending.
   - **Observations**: a bullet-point list of automatically generated observations (e.g.,
     highest-accuracy combination, lowest FAR, lowest FRR).
   - **Conclusion**: a paragraph naming the best-performing (Detector, Recognizer)
     combination and summarising its metrics.
3. THE Report_Generator SHALL embed relative links to all generated plot images within
   the report.

---

### Requirement 10: Configuration

**User Story:** As a researcher, I want all experiment parameters to be controlled from a
single YAML config file, so that I can reproduce any experiment by sharing one file.

#### Acceptance Criteria

1. THE Pipeline SHALL read all tunable parameters from
   `configs/experiment_config.yaml` at startup.
2. THE Config SHALL support the following parameters:
   - `dataset_path`: path to the raw dataset directory.
   - `gallery_ratio`: float in (0, 1) controlling the gallery/probe split (default 0.70).
   - `random_seed`: integer for reproducible shuffling (default 42).
   - `image_size`: list `[width, height]` for preprocessing resize (default [640, 640]).
   - `detectors`: list of detector names to enable (e.g., `["insightface", "haarcascade",
     "retinaface"]`).
   - `recognizers`: list of recognizer names to enable (e.g., `["insightface", "lbph",
     "dlib"]`).
   - `similarity_threshold`: float used as the match/no-match decision boundary for
     embedding-based recognizers (default 0.85).
   - `output_dir`: path to the results output directory (default `results/`).
3. IF a required Config key is missing, THEN THE Experiment_Runner SHALL raise a
   `ValueError` with a message identifying the missing key and halt before any Experiment
   begins.

---

### Requirement 11: Interactive Setup Prompt

**User Story:** As a researcher, I want to be prompted for key parameters when I first
run the pipeline, so that I do not have to manually edit the config file for common
adjustments.

#### Acceptance Criteria

1. WHEN `run_experiments.py` is executed with the `--interactive` flag, THE
   Experiment_Runner SHALL prompt the user to enter: the dataset path, the gallery split
   ratio, and the list of models to run.
2. THE Experiment_Runner SHALL validate that the entered dataset path exists and contains
   at least one Identity sub-folder; IF the path is invalid, THEN THE Experiment_Runner
   SHALL re-prompt the user up to 3 times before exiting with a descriptive error
   message.
3. WHEN the user provides interactive inputs, THE Experiment_Runner SHALL write the
   resulting configuration to `configs/experiment_config.yaml`, overwriting any previous
   values, before starting the Experiments.

---

### Requirement 12: Reproducibility and Logging

**User Story:** As a researcher, I want every experiment run to be fully reproducible and
traceable, so that I can report exact conditions in a paper.

#### Acceptance Criteria

1. THE Experiment_Runner SHALL record the following metadata for each run in
   `results/logs/experiment_log.txt`: timestamp, Python version, library versions for
   all enabled models, Config file contents (as YAML), and random seed used.
2. THE Experiment_Runner SHALL set the NumPy and Python random seeds to the value
   specified in Config before any data splitting or model inference occurs.
3. WHEN an Experiment fails due to an unhandled exception, THE Experiment_Runner SHALL
   log the full stack trace to `results/logs/experiment_log.txt`, mark that Experiment
   as failed in the summary CSV, and continue with the remaining Experiments.

---

### Requirement 13: Dependency Isolation

**User Story:** As a researcher, I want the evaluation pipeline's dependencies to be
listed separately, so that installing them does not conflict with the production backend.

#### Acceptance Criteria

1. THE Pipeline SHALL provide `backend/evaluation/requirements-evaluation.txt` listing
   all required packages with pinned major versions.
2. THE requirements-evaluation.txt SHALL include at minimum: `opencv-python`, `numpy`,
   `insightface`, `onnxruntime`, `retinaface`, `face_recognition`, `dlib`, `pyyaml`,
   `matplotlib`, `seaborn`, `pandas`, `scikit-learn`.
3. THE Pipeline SHALL include a `README_EVALUATION.md` at `backend/evaluation/` with
   step-by-step instructions for: creating a virtual environment, installing
   requirements-evaluation.txt, placing the dataset, and running `run_experiments.py`.

---

### Requirement 14: Ground Truth Handling

**User Story:** As a researcher, I want to supply optional bounding box annotations per
identity, so that detection precision and recall are computed against real ground truth
rather than the single-face approximation.

#### Acceptance Criteria

1. THE Pipeline SHALL support an optional `annotations.json` file inside each Identity
   sub-folder under `dataset/raw/`, mapping image filename to a list of bounding boxes
   in the format `{"image_filename.jpg": [[x1, y1, x2, y2], ...], ...}`.
2. WHEN `annotations.json` is present for an Identity, THE Metrics_Engine SHALL use the
   provided bounding boxes as ground truth and compute IoU-based Precision and Recall
   (IoU threshold ≥ 0.5) for that Identity's images.
3. WHEN `annotations.json` is absent for an Identity, THE Metrics_Engine SHALL fall back
   to the approximate single-face detection rate defined in Requirement 6, criterion 2.
4. THE Dataset_Splitter SHALL load identity labels from sub-folder names regardless of
   whether `annotations.json` is present, preserving backward compatibility with
   unannotated datasets.
5. IF `annotations.json` exists but cannot be parsed as valid JSON, THEN THE
   Dataset_Splitter SHALL log a warning identifying the malformed file and treat that
   Identity as unannotated.

---

### Requirement 15: Threshold Calibration

**User Story:** As a researcher, I want the pipeline to compute both a fixed-threshold
and an Equal Error Rate threshold, so that I can report calibrated performance metrics
alongside the default configuration.

#### Acceptance Criteria

1. THE Metrics_Engine SHALL evaluate recognition metrics at the fixed
   `similarity_threshold` value read from the Config (as defined in Requirement 10).
2. THE Metrics_Engine SHALL compute the Equal Error Rate (EER) threshold: the similarity
   threshold at which FAR equals FRR, determined by sweeping threshold values across the
   range of observed similarity scores.
3. THE Metrics_Engine SHALL report accuracy, FAR, and FRR at both the fixed threshold
   and the EER threshold side by side in `results/logs/recognition_metrics.csv`, adding
   columns: `EER_threshold`, `accuracy_at_EER`, `FAR_at_EER`, `FRR_at_EER`.
4. THE Report_Generator SHALL save a threshold sweep curve (FAR and FRR plotted against
   threshold value) for each Experiment to
   `results/plots/threshold_sweep_<detector>_<recognizer>.png`.
5. WHEN generating the threshold sweep, THE Metrics_Engine SHALL evaluate at a minimum
   of 100 evenly spaced threshold values spanning the full range of observed similarity
   scores.

---

### Requirement 16: Open-Set Recognition Evaluation

**User Story:** As a researcher, I want to evaluate the pipeline in open-set mode, so
that I can measure how well it rejects probe images from identities not present in the
gallery.

#### Acceptance Criteria

1. THE Config SHALL support an `open_set_ratio` parameter: a float in [0.0, 1.0)
   specifying the fraction of identities to withhold entirely from the Gallery Set
   (default 0.0, which corresponds to closed-set evaluation).
2. WHEN `open_set_ratio` is greater than 0.0, THE Dataset_Splitter SHALL randomly
   select `floor(num_identities × open_set_ratio)` identities as unknown identities,
   exclude them from the Gallery Set, and include their images in the Probe Set as
   unknown probes.
3. WHEN a Recognizer's `predict` method is called in open-set mode and the best-match
   similarity score is below `similarity_threshold`, THE Recognizer SHALL return the
   label `"unknown"` instead of a gallery identity label.
4. THE Metrics_Engine SHALL compute the following additional open-set metrics per
   Experiment when `open_set_ratio` > 0.0:
   - **Open-Set Detection Rate**: fraction of unknown probes correctly returned as
     `"unknown"`.
   - **False Alarm Rate**: fraction of unknown probes incorrectly assigned a gallery
     identity label.
5. THE Metrics_Engine SHALL append open-set metrics to
   `results/logs/recognition_metrics.csv` in additional columns:
   `open_set_detection_rate`, `false_alarm_rate` (populated only when
   `open_set_ratio` > 0.0; otherwise left empty).

---

### Requirement 17: Condition-Wise Performance Analysis

**User Story:** As a researcher, I want per-condition breakdowns of recognition
performance, so that I can identify which lighting or pose conditions degrade accuracy
the most.

#### Acceptance Criteria

1. THE Pipeline SHALL support an optional `conditions.json` file inside each Identity
   sub-folder under `dataset/raw/`, mapping image filename to a condition dictionary in
   the format `{"image_filename.jpg": {"lighting": "<value>", "angle": "<value>"}, ...}`.
2. WHEN `conditions.json` is present for an Identity, THE Metrics_Engine SHALL group
   Probe images by each condition type (`lighting`, `angle`) and compute accuracy, FAR,
   and FRR separately for each distinct condition value.
3. WHEN `conditions.json` is absent for all identities, THE Metrics_Engine SHALL skip
   condition-wise analysis and omit the corresponding output files without raising an
   error.
4. THE Report_Generator SHALL save a bar chart of accuracy broken down by condition
   value for each condition type to
   `results/plots/condition_analysis_<condition_type>.png`.
5. THE Metrics_Engine SHALL write condition-wise metrics to
   `results/logs/condition_metrics.csv` with columns: `detector`, `recognizer`,
   `condition_type`, `condition_value`, `accuracy`, `FAR`, `FRR`.

---

### Requirement 18: Inference Time Benchmarking

**User Story:** As a researcher, I want per-image timing measurements for detection and
recognition, so that I can report the computational cost of each pipeline configuration.

#### Acceptance Criteria

1. FOR EACH Probe image processed in an Experiment, THE Experiment_Runner SHALL measure
   and record: detection time in milliseconds, recognition/embedding time in
   milliseconds, and total pipeline time per image in milliseconds.
2. THE Metrics_Engine SHALL compute the following timing statistics across all Probe
   images per Experiment: mean, median, standard deviation, minimum, and maximum for
   each of the three timing measurements.
3. THE Experiment_Runner SHALL save per-image timing records to
   `results/logs/timing_<detector>_<recognizer>.csv` with columns: `image_path`,
   `detection_ms`, `recognition_ms`, `total_ms`.
4. THE Report_Generator SHALL include a timing summary table in `final_report.md` with
   columns: `Detector`, `Recognizer`, `Mean Detection (ms)`, `Mean Recognition (ms)`,
   `Mean Total (ms)`, `Std Total (ms)`.
5. WHEN measuring timing, THE Experiment_Runner SHALL use a monotonic high-resolution
   clock and SHALL NOT include image loading or preprocessing time in the detection or
   recognition measurements.

---

### Requirement 19: Embedding Space Analysis

**User Story:** As a researcher, I want intra-class and inter-class distance metrics and
a 2D embedding visualisation, so that I can assess the separability of the learned
embedding space.

#### Acceptance Criteria

1. AFTER building the Gallery for an embedding-based Recognizer (InsightFace or dlib),
   THE Metrics_Engine SHALL compute:
   - **Intra-class distance**: mean pairwise Euclidean distance between all Gallery
     embeddings belonging to the same Identity.
   - **Inter-class distance**: mean pairwise Euclidean distance between Gallery
     embeddings belonging to different Identities.
   - **Fisher Discriminant Ratio (FDR)**: inter-class distance divided by intra-class
     distance; a higher value indicates better embedding separability.
2. THE Metrics_Engine SHALL write embedding space metrics to
   `results/logs/embedding_metrics.csv` with columns: `recognizer`,
   `intra_class_distance`, `inter_class_distance`, `fisher_discriminant_ratio`.
3. THE Report_Generator SHALL produce a 2D scatter plot of all Gallery embeddings
   reduced via t-SNE (preferred) or PCA, coloured by Identity, and save it to
   `results/plots/embedding_space_<recognizer>.png`.
4. WHERE the Recognizer is LBPH (which does not produce fixed-length embeddings), THE
   Metrics_Engine SHALL skip embedding space analysis for that Recognizer and log an
   informational message.
5. WHEN computing pairwise distances for embedding space analysis, THE Metrics_Engine
   SHALL use the same distance metric as the Recognizer uses for matching (Euclidean for
   InsightFace, cosine for dlib).

---

### Requirement 20: Failure Case Logging

**User Story:** As a researcher, I want annotated images of all misclassified probes
saved to disk, so that I can visually inspect failure modes and include representative
examples in a paper.

#### Acceptance Criteria

1. FOR EACH Experiment, THE Experiment_Runner SHALL identify all Probe images where the
   predicted identity label does not equal the true identity label.
2. THE Experiment_Runner SHALL save each misclassified Probe image to
   `results/logs/failures/<detector>_<recognizer>/`, annotating the image with the true
   label, predicted label, and similarity score overlaid as text before saving.
3. THE Experiment_Runner SHALL write a failure summary CSV to
   `results/logs/failures/<detector>_<recognizer>_failures.csv` with columns:
   `image_path`, `true_label`, `predicted_label`, `similarity_score`, `condition`
   (populated from `conditions.json` if available; otherwise left empty).
4. IF no misclassifications occur in an Experiment, THE Experiment_Runner SHALL create
   an empty `<detector>_<recognizer>_failures.csv` with the header row only and log an
   informational message indicating zero failures.
5. WHEN annotating failure images, THE Experiment_Runner SHALL render text at a font
   size legible at the saved image resolution and SHALL use a contrasting colour so that
   the annotation is visible against any background.

---

### Requirement 21: Statistical Evaluation Across Multiple Runs

**User Story:** As a researcher, I want the pipeline to repeat each experiment over
multiple random splits and report mean ± standard deviation, so that my results are
statistically robust rather than dependent on a single data split.

#### Acceptance Criteria

1. THE Config SHALL support a `num_runs` parameter: a positive integer specifying how
   many times each Experiment is repeated with a different random split (default 1).
2. WHEN `num_runs` is greater than 1, THE Dataset_Splitter SHALL generate a distinct
   gallery/probe split for each run by using a seed equal to `random_seed + run_index`
   (where `run_index` starts at 0), ensuring splits differ across runs while remaining
   reproducible.
3. THE Experiment_Runner SHALL save per-run prediction records to
   `results/logs/<detector>_<recognizer>_run_<n>_predictions.csv` (where `<n>` is the
   zero-based run index) using the same column schema as the single-run predictions CSV
   defined in Requirement 5.
4. THE Metrics_Engine SHALL compute mean and standard deviation for accuracy, FAR, and
   FRR across all runs per Experiment, and SHALL write these aggregated statistics to
   `results/logs/recognition_metrics.csv` in additional columns: `accuracy_mean`,
   `accuracy_std`, `FAR_mean`, `FAR_std`, `FRR_mean`, `FRR_std`.
5. THE Report_Generator SHALL include mean ± standard deviation values and 95 %
   confidence intervals in the Model Comparison Table of `final_report.md` when
   `num_runs` is greater than 1.
6. WHEN `num_runs` equals 1, THE Experiment_Runner SHALL behave identically to the
   single-run behaviour defined in Requirement 5, with no additional output files
   generated.
