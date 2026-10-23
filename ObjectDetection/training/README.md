# Fine-tuning PPE and materials models

Train on a connected machine, export ONNX, then copy the file into `models/` and pin its sha256 in `models/manifest.json`. The running dashboard never downloads weights.

## PPE

1. Label helmet, vest, gloves, boots, and the negative classes (`no_helmet`, `no_vest`, `no_gloves`) in CVAT or Label Studio.
2. Export YOLO detection labels. Point `training/datasets.yaml` at that folder.
3. Run `python training/train_ppe.py --data training/datasets.yaml --weights path/to/local.pt`.
4. Export with `python scripts/export_models.py --weights runs/detect/train/weights/best.pt`.

Public starting sets (check each license): SH17, Construction Site Safety, CHV, SHWD. Target a helmet/vest F1 of at least 0.90 on your own site footage.

## Materials and machinery

There is no reliable public set for rebar, gypsum, cement bags, and the rest of `config/classes.yaml`. Label at least 500 images per class, including stacked, dusty, and partly hidden examples. Negative frames of an empty site cut false counts.

`training/train_materials.py` uses the same local-weights rule. Turn tiling on in camera settings (`detector.materials.tile`) when the objects are small in the frame.

## Posture

Posture is rule-based on COCO-17 keypoints (`docs/04-CLASSES-AND-RULES.md`). Collect 300–1000 clips of lying, crawling, and sitting from your cameras before replacing the rules with a sequence model.
