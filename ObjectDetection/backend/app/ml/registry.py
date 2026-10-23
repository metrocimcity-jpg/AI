"""Read models/manifest.json. Weights are never downloaded."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.core.logging import get_logger

logger = get_logger("siteguard.ml.registry")

_UNPINNED = {"", "..."}


class ModelError(RuntimeError):
    """Base error for local model loading."""


class ModelMissingError(ModelError):
    """The manifest entry points at a file that is not on disk."""


class ModelHashError(ModelError):
    """sha256 of the file does not match the manifest."""


@dataclass
class ModelSpec:
    name: str
    path: Path
    sha256: str
    task: str
    imgsz: int
    classes: list[str]
    license: str
    dim: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ModelRegistry:
    def __init__(self, root: Path, manifest_path: Path | None = None) -> None:
        self.root = root
        self.models_dir = root / "models"
        self.manifest_path = manifest_path or (self.models_dir / "manifest.json")
        self._specs = self._load()

    def _load(self) -> dict[str, ModelSpec]:
        if not self.manifest_path.is_file():
            raise ModelMissingError(
                f"Model manifest not found at {self.manifest_path}. "
                "SiteGuard never downloads models automatically."
            )
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        specs: dict[str, ModelSpec] = {}
        for name, entry in data.items():
            classes = list(entry.get("classes") or [])
            classes_file = entry.get("classes_file")
            if not classes and classes_file:
                classes = self._classes_from_file(str(classes_file))
            rel = Path(str(entry["path"]))
            path = rel if rel.is_absolute() else self.models_dir / rel
            specs[name] = ModelSpec(
                name=name,
                path=path,
                sha256=str(entry.get("sha256") or ""),
                task=str(entry.get("task") or "detect"),
                imgsz=int(entry.get("imgsz") or 640),
                classes=classes,
                license=str(entry.get("license") or "unknown"),
                dim=int(entry["dim"]) if entry.get("dim") else None,
                raw=dict(entry),
            )
        return specs

    def _classes_from_file(self, ref: str) -> list[str]:
        file_part, _, key = ref.partition("#")
        path = self.root / file_part
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        value = loaded.get(key, []) if key else loaded
        if not isinstance(value, list):
            raise ModelError(f"classes file {ref} did not contain a list")
        return [str(item) for item in value]

    def reload(self) -> None:
        self._specs = self._load()

    def names(self) -> list[str]:
        return list(self._specs)

    def get(self, name: str) -> ModelSpec:
        if name not in self._specs:
            known = ", ".join(self._specs) or "(none)"
            raise ModelMissingError(
                f"Model {name!r} is not listed in {self.manifest_path}. Known models: {known}. "
                "SiteGuard never downloads models automatically."
            )
        spec = self._specs[name]
        if not spec.path.is_file():
            raise ModelMissingError(
                f"Model {name!r} is not available at {spec.path}. "
                "Copy the ONNX file into the models directory and update models/manifest.json. "
                "SiteGuard never downloads models automatically."
            )
        if spec.sha256 not in _UNPINNED:
            actual = file_sha256(spec.path)
            if actual.lower() != spec.sha256.lower():
                raise ModelHashError(
                    f"sha256 mismatch for {name!r}: manifest {spec.sha256} != file {actual}."
                )
        elif spec.sha256 in _UNPINNED:
            logger.warning("model %s has no sha256 pin; set it in models/manifest.json", name)
        return spec

    def status(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for spec in self._specs.values():
            rows.append(
                {
                    "name": spec.name,
                    "path": spec.path.name,
                    "task": spec.task,
                    "license": spec.license,
                    "imgsz": spec.imgsz,
                    "exists": spec.path.is_file(),
                    "sha256_pinned": spec.sha256 not in _UNPINNED,
                    "loaded": False,
                }
            )
        return rows
