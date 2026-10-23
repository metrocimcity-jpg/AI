"""ONNX Runtime execution-provider order."""

from __future__ import annotations

PROVIDER_NAMES = {
    "tensorrt": "TensorrtExecutionProvider",
    "cuda": "CUDAExecutionProvider",
    "openvino": "OpenVINOExecutionProvider",
    "directml": "DmlExecutionProvider",
    "cpu": "CPUExecutionProvider",
}


def select_providers(priority: list[str], available: list[str]) -> list[str]:
    chosen: list[str] = []
    for name in priority:
        ort_name = PROVIDER_NAMES.get(name.lower())
        if ort_name and ort_name in available and ort_name not in chosen:
            chosen.append(ort_name)
    if "CPUExecutionProvider" in available and "CPUExecutionProvider" not in chosen:
        chosen.append("CPUExecutionProvider")
    if not chosen:
        chosen.append("CPUExecutionProvider")
    return chosen
