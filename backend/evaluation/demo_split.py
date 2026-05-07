"""
Demo script — shows DatasetSplitter in action with a synthetic dataset.

Run from backend/evaluation/:
    python demo_split.py
"""

import sys
from pathlib import Path

# Ensure current directory is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import cv2
from configs.config import ExperimentConfig
from utils.image_loader import DatasetSplitter


def create_demo_dataset():
    """Create a small synthetic dataset under dataset/raw/."""
    raw = Path("dataset/raw")
    raw.mkdir(parents=True, exist_ok=True)

    # Simulate 3 identities with varying image counts
    identities = {
        "1032221489": 50,
        "1032220455": 75,
        "1032221234": 100,
    }

    for prn, n_images in identities.items():
        id_dir = raw / prn
        id_dir.mkdir(exist_ok=True)
        for i in range(n_images):
            img_path = id_dir / f"img{i:04d}.jpg"
            if not img_path.exists():
                # Create a small random image
                img = np.random.randint(100, 200, (50, 50, 3), dtype=np.uint8)
                cv2.imwrite(str(img_path), img)

    print(f"[INFO] Created synthetic dataset under: {raw.resolve()}")
    return raw


def main():
    print("=" * 60)
    print("  DatasetSplitter Demo")
    print("=" * 60)

    # Create synthetic dataset
    raw = create_demo_dataset()

    # Load config
    cfg = ExperimentConfig.from_yaml("configs/experiment_config.yaml")
    print(f"\n[INFO] Loaded config from: configs/experiment_config.yaml")
    print(f"  Gallery ratio   : {cfg.gallery_ratio}")
    print(f"  Random seed     : {cfg.random_seed}")
    print(f"  Open-set ratio  : {cfg.open_set_ratio}")

    # Create splitter
    splitter = DatasetSplitter(cfg, min_images=10)

    # Run split for run_index=0
    print("\n[INFO] Running split for run_index=0...")
    result = splitter.split(run_index=0)

    # Print summary
    splitter.print_summary(result)

    # Show a few sample paths
    print("\n" + "=" * 60)
    print("  Sample Gallery Paths (first 3 per identity)")
    print("=" * 60)
    for prn in sorted(result.gallery.keys()):
        paths = result.gallery[prn][:3]
        print(f"  {prn}:")
        for p in paths:
            print(f"    - {p.name}")

    print("\n" + "=" * 60)
    print("  Sample Probe Paths (first 3 per identity)")
    print("=" * 60)
    for prn in sorted(result.probe.keys()):
        paths = result.probe[prn][:3]
        print(f"  {prn}:")
        for p in paths:
            print(f"    - {p.name}")

    print("\n[INFO] Demo complete.")


if __name__ == "__main__":
    main()
