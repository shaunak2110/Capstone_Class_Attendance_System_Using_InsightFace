# Face Recognition Evaluation Pipeline

A research-grade, standalone evaluation pipeline for comparing multiple face detection
and recognition models on a classroom dataset. Produces quantitative metrics,
publication-quality charts, and a structured Markdown report.

> **Important:** This module is completely independent of the production backend.
> It does not import from or modify any file outside `backend/evaluation/`.

---

## Quick Start

### 1. Create a virtual environment

```bash
# From the workspace root
python -m venv .venv-eval

# Activate — Windows
.venv-eval\Scripts\activate

# Activate — Linux / macOS
source .venv-eval/bin/activate
```

### 2. Install dependencies

```bash
pip install -r backend/evaluation/requirements-evaluation.txt
```

> **Note on dlib / face_recognition:** On Windows, `dlib` requires CMake and a C++
> compiler. If installation fails, install the pre-built wheel:
> ```bash
> pip install dlib‑<version>‑cp<pyver>‑win_amd64.whl
> pip install face-recognition
> ```
> If you skip dlib, the pipeline will automatically skip the `dlib` recognizer and
> continue with the remaining models.

### 3. Place your dataset

Organise images under `backend/evaluation/dataset/raw/` with one sub-folder per identity:

```
backend/evaluation/dataset/raw/
├── 1032221489/
│   ├── img001.jpg
│   ├── img002.jpg
│   └── ...
├── 1032220455/
│   ├── img001.jpg
│   └── ...
└── ...
```

Each identity folder must contain **at least 2 images**. Supported formats: `.jpg`,
`.jpeg`, `.png`, `.bmp` (case-insensitive).

#### Optional: bounding box annotations

Add `annotations.json` inside an identity folder to enable IoU-based detection metrics:

```json
{
  "img001.jpg": [[120, 80, 300, 260]],
  "img002.jpg": [[95, 70, 280, 250]]
}
```

Format: `{ "filename": [[x1, y1, x2, y2], ...], ... }`

#### Optional: condition tags

Add `conditions.json` inside an identity folder to enable condition-wise analysis:

```json
{
  "img001.jpg": {"lighting": "bright", "angle": "frontal"},
  "img002.jpg": {"lighting": "dim",    "angle": "profile"}
}
```

### 4. Configure the experiment

Edit `backend/evaluation/configs/experiment_config.yaml`:

```yaml
dataset_path: dataset/raw
gallery_ratio: 0.70          # 70% gallery, 30% probe
random_seed: 42
image_size: [640, 640]

detectors:
  - insightface
  - haarcascade
  - retinaface

recognizers:
  - insightface
  - lbph
  - dlib

similarity_threshold: 0.85
output_dir: results/
open_set_ratio: 0.0          # 0.0 = closed-set; >0 enables open-set evaluation
num_runs: 1                  # >1 enables statistical multi-run evaluation
```

### 5. Run experiments

```bash
# From backend/evaluation/
cd backend/evaluation
python run_experiments.py
```

#### Interactive mode (guided setup)

```bash
python run_experiments.py --interactive
```

This prompts you for dataset path, split ratio, and model selection, then writes the
config before running.

---

## Output

All results are written to `backend/evaluation/results/`:

```
results/
├── logs/
│   ├── experiment_log.txt              # timestamps, versions, config, stack traces
│   ├── detection_metrics.csv           # per-detector detection rate, precision, recall
│   ├── recognition_metrics.csv         # per-experiment accuracy, FAR, FRR, EER
│   ├── condition_metrics.csv           # per-condition accuracy/FAR/FRR (if conditions.json present)
│   ├── embedding_metrics.csv           # intra/inter-class distance, Fisher ratio
│   ├── timing_<det>_<rec>.csv          # per-image detection and recognition timing
│   ├── <det>_<rec>_predictions.csv     # per-image predictions
│   └── failures/
│       ├── <det>_<rec>/                # annotated failure images
│       └── <det>_<rec>_failures.csv
├── plots/
│   ├── accuracy_comparison.png
│   ├── far_frr_comparison.png
│   ├── det_curve.png
│   ├── <det>_<rec>_confusion_matrix.png
│   ├── threshold_sweep_<det>_<rec>.png
│   ├── condition_analysis_<type>.png
│   └── embedding_space_<recognizer>.png
└── reports/
    └── final_report.md                 # structured research report
```

---

## Running Tests

```bash
# From the workspace root, with the virtual environment active
python -m pytest backend/evaluation/tests/ -v
```

To run only the config tests:

```bash
python -m pytest backend/evaluation/tests/test_config.py -v
```

---

## Model Files

The InsightFace detector and recognizer require the `buffalo_l` model pack. The pipeline
looks for model files relative to the workspace root:

| Model | Path |
|---|---|
| Detector | `buffalo_l/det_10g.onnx` |
| Recognizer | `buffalo_l/w600k_r50.onnx` |

These files are already present in the workspace (`buffalo_l/` at the root). The
evaluation pipeline references them via a relative path from `backend/evaluation/`.

---

## Supported Models

| Type | Name | Backend | Notes |
|---|---|---|---|
| Detector | `insightface` | InsightFace buffalo_l | Requires `buffalo_l/det_10g.onnx` |
| Detector | `haarcascade` | OpenCV | Ships with `opencv-python` |
| Detector | `retinaface` | `retina-face` package | Pure Python |
| Detector | `yolo` | Ultralytics YOLO | Optional; skipped if model file absent |
| Recognizer | `insightface` | ArcFace 512-dim | Requires `buffalo_l/w600k_r50.onnx` |
| Recognizer | `lbph` | OpenCV LBPH | No model file needed |
| Recognizer | `dlib` | `face_recognition` | Requires dlib + model download |

---

## Reproducibility

Every experiment run is fully reproducible. Share `configs/experiment_config.yaml` and
the dataset to reproduce any result exactly. The `random_seed` controls all shuffling
and splits.
