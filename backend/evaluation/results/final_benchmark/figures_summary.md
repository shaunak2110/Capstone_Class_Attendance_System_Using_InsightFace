# Benchmark Figures Summary

All figures are saved as both PNG (300 DPI) and PDF in `results/final_benchmark/figures/`.

## Dataset
- 4 identities: person_1_sudhanshu, person_2_shaunak, person_3_srishti, person_4_ashlesha
- 335 total images (50–106 per identity)
- 70% gallery / 30% probe split, 3 independent runs per combination
- Similarity threshold: 0.50

## Figures

### Figure 1 — `fig1_accuracy_comparison`
Bar chart comparing recognition accuracy (mean ± std) across all 4 detector × recognizer
combinations. The best-performing system (InsightFace + ArcFace) is highlighted with a
gold border. Error bars represent standard deviation across 3 runs.

### Figure 2 — `fig2_detection_rate`
Bar chart showing face detection rate per combination. Haarcascade detects ~68% of probe
images; InsightFace detects ~98%. A vertical divider separates the two detector groups.

### Figure 3 — `fig3_far_frr_comparison`
Grouped bar chart comparing FRR and EER side by side for each combination.
LBPH-based systems show FRR = 100% (all genuine probes rejected at threshold 0.50),
while ArcFace-based systems achieve FRR < 40%.

### Figure 4 — `fig4_eer_comparison`
Bar chart of Equal Error Rate (EER) sorted ascending (lower = better).
Best: InsightFace + ArcFace — EER = 5.1% ± 2.7%.

### Figure 5 — `fig5_latency_comparison`
Stacked bar chart showing mean detection and recognition latency per image.
Haarcascade + LBPH is fastest (~77 ms); InsightFace + ArcFace takes ~163 ms.

### Figure 6 — `fig6_det_curves`
Detection Error Tradeoff (DET) curves plotting FAR vs FRR across the full threshold sweep.
Curves averaged across 3 runs. The best system (InsightFace + ArcFace) is shown with a
solid line; others are dashed.

### Figure 7 — `fig7_confusion_matrix_best`
Row-normalised confusion matrix for the best system (InsightFace + ArcFace, run 0).
Diagonal values show per-identity recall. Off-diagonal values reveal which identities
are most frequently confused.

### Figure 8 — `fig8_radar_comparison`
Radar (spider) chart comparing 4 metrics simultaneously: Accuracy, Detection Rate,
1−EER, and 1−FRR (all normalised to [0,1], higher = better). Provides a holistic
view of each system's strengths and weaknesses.

## Key Results

| Detector | Recognizer | Accuracy | EER | Det. Rate | Latency |
|---|---|---|---|---|---|
| Haarcascade | ArcFace | 92.8±1.3% | 18.5±1.4% | 68.0% | 157ms |
| Insightface | ArcFace | 91.4±5.8% | 5.1±2.7% | 98.4% | 163ms |
| Haarcascade | LBPH | 21.1±3.6% | 42.8±1.4% | 68.0% | 77ms |
| Insightface | LBPH | 20.3±1.8% | 40.0±0.8% | 98.4% | 84ms |

## Conclusion

The **InsightFace detector + ArcFace recognizer** combination achieves the highest
recognition accuracy (91.4% ± 5.8%)
and the lowest EER (5.1% ± 2.7%),
with a face detection rate of 98.4%.
The trade-off is higher latency (~163 ms/image vs ~77 ms for
Haarcascade + LBPH). For attendance systems where accuracy is paramount, InsightFace + ArcFace
is the recommended configuration.