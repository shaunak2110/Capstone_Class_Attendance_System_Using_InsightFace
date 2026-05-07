"""Quick analysis of the latest InsightFace experiment results."""
import sys, csv, statistics, math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

exp_dirs = sorted(Path(__file__).parent / "results" / "experiments" for _ in [1])
# Find the most recent experiment with insightface predictions
base = Path(__file__).parent / "results" / "experiments"
csv_path = None
for exp_dir in sorted(base.iterdir(), reverse=True):
    candidates = list(exp_dir.glob("predictions_insightface_insightface*.csv"))
    if candidates:
        csv_path = candidates[0]
        print(f"Analyzing: {csv_path}")
        break

if csv_path is None:
    print("No insightface predictions CSV found.")
    sys.exit(1)

rows = list(csv.DictReader(open(csv_path)))
detected = [r for r in rows if r["detected"] == "True"]
print(f"\nTotal probes:              {len(rows)}")
print(f"Detected:                  {len(detected)}")
print(f"Embedding failures:        {len(rows) - len(detected)}")

genuine  = [float(r["similarity"]) for r in detected if r["true_label"] == r["predicted_label"]]
impostor = [float(r["similarity"]) for r in detected if r["true_label"] != r["predicted_label"]]

def stats(vals, label):
    if not vals:
        print(f"  {label}: N/A")
        return
    n = len(vals)
    m = sum(vals) / n
    std = math.sqrt(sum((v - m) ** 2 for v in vals) / n)
    print(f"  {label}:")
    print(f"    n={n}  mean={m:.4f}  std={std:.4f}  "
          f"min={min(vals):.4f}  max={max(vals):.4f}  "
          f"median={statistics.median(vals):.4f}")

print()
stats(genuine,  "Genuine  (correct match) similarity")
stats(impostor, "Impostor (wrong match)   similarity")

print()
print("Threshold sweep (closed-set accuracy):")
print(f"  {'Threshold':>10} {'Correct':>8} {'Total':>7} {'Accuracy':>10}")
for t in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]:
    correct = sum(
        1 for r in detected
        if r["true_label"] == r["predicted_label"] and float(r["similarity"]) >= t
    )
    total = len(detected)
    acc = correct / total if total > 0 else 0
    marker = " <- current threshold" if abs(t - 0.85) < 0.001 else ""
    print(f"  {t:>10.2f} {correct:>8} {total:>7} {acc:>10.4f}{marker}")

print()
print("Top 20 correct matches (highest similarity):")
correct_rows = sorted(
    [r for r in detected if r["true_label"] == r["predicted_label"]],
    key=lambda x: float(x["similarity"]), reverse=True
)[:20]
for r in correct_rows:
    name = Path(r["image_id"]).name
    print(f"  {name:<50} {r['true_label']:<25} sim={float(r['similarity']):.4f}")

print()
print("Top 20 wrong predictions (highest similarity, genuine rejected):")
wrong_rows = sorted(
    [r for r in detected if r["true_label"] != r["predicted_label"]],
    key=lambda x: float(x["similarity"]), reverse=True
)[:20]
for r in wrong_rows:
    name = Path(r["image_id"]).name
    print(f"  {name:<50} true={r['true_label']:<22} pred={r['predicted_label']:<22} sim={float(r['similarity']):.4f}")
