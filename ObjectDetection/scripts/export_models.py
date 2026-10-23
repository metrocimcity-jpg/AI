"""Export a local .pt file to ONNX. Run this only on a connected machine.

This script does not download weights. Pass a file you already have.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a local checkpoint to ONNX")
    parser.add_argument("--weights", required=True, help="Path to a local .pt file")
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args(argv)
    weights = Path(args.weights)
    if not weights.is_file():
        print(f"Weights not found: {weights}. SiteGuard never downloads models.")
        return 1
    try:
        from ultralytics import YOLO
    except ImportError:
        print("Install ultralytics on the connected build machine, then re-run.")
        print(f"Example: yolo export model={weights} format=onnx imgsz={args.imgsz} opset=17")
        return 1
    model = YOLO(str(weights))
    model.export(format="onnx", imgsz=args.imgsz, opset=17, simplify=True, dynamic=False)
    print("Export finished. Copy the .onnx file into models/ and set sha256 in manifest.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
