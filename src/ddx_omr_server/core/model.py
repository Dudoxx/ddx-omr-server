"""The checkbox classifier: verified once at startup, run once per request.

The weights are AGPL-3.0 (hermitkk/omr-checkbox-classifier). They are loaded
only after their SHA-256 matches the pinned value; any mismatch or a missing
file raises, so the service refuses to start instead of scoring with
unknown weights.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
import onnxruntime as ort

MODEL_NAME = "hermitkk/omr-checkbox-classifier"


class ModelError(RuntimeError):
    """The weights are missing, unverifiable, or cannot be loaded."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ModelInfo:
    name: str
    revision: str
    sha256: str


class CheckboxModel:
    """One ONNX session on the CPU, shared by every request."""

    def __init__(self, path: Path, expected_sha256: str, revision: str) -> None:
        if not path.is_file():
            raise ModelError(
                f"weights not found at {path}. Run scripts/fetch-weights.sh first."
            )
        actual = sha256_of(path)
        if actual != expected_sha256:
            raise ModelError(
                f"weights SHA-256 mismatch at {path}: expected {expected_sha256}, "
                f"got {actual}. Refusing to start."
            )
        try:
            self._session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        except Exception as exc:  # onnxruntime raises its own untyped errors
            raise ModelError(f"cannot load weights at {path}: {exc}") from exc
        self._input = self._session.get_inputs()[0].name
        self.info = ModelInfo(name=MODEL_NAME, revision=revision, sha256=actual)

    def probabilities(self, batch: npt.NDArray[np.float32]) -> npt.NDArray[np.float64]:
        """Score a (N, 64, 64) batch in one run; returns N sigmoid probabilities."""
        if batch.shape[0] == 0:
            return np.zeros(0, dtype=np.float64)
        outputs = self._session.run(None, {self._input: batch[:, None, :, :]})
        logits = np.asarray(outputs[0], dtype=np.float64).reshape(batch.shape[0], -1)[:, 0]
        return 1.0 / (1.0 + np.exp(-logits))
