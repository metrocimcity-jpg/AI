"""Fine-tune a local detector. Refuses to start without a local checkpoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="training/datasets.yaml")
    parser.add_argument("--weights", required=True)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()
    weights = Path(args.weights)
    data = Path(args.data)
    if not weights.is_file() or not data.is_file():
        print("Both --weights and --data must be local files. Nothing is downloaded.")
        return 1
    try:
        from ultralytics import YOLO
    except ImportError:
        print("Install ultralytics on the training machine first.")
        return 1
    YOLO(str(weights)).train(data=str(data), epochs=args.epochs, imgsz=args.imgsz, device="cpu")
    return 0


if __name__ == "__main__":
    sys.exit(main())
