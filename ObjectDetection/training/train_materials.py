"""Fine-tune the materials model from a local checkpoint and dataset yaml."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.argv[0] = "train_materials.py"
    script = Path(__file__).with_name("train_ppe.py")
    raise SystemExit(runpy.run_path(str(script), run_name="__main__"))
