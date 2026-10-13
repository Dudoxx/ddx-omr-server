"""Service configuration, read once from the environment.

Every value has a default in code and a value in ``.env``; nothing here is
hard-coded into a route. An empty API key or a malformed number refuses to
start — the service never degrades to an unauthenticated or guessed mode.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ddx_omr_server import __version__

SERVICE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_PATH = "models/omr_model.onnx"


class SettingsError(RuntimeError):
    """The environment cannot produce a valid configuration."""


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    host: str
    port: int
    log_level: str
    api_key: str
    cors_origins: tuple[str, ...]
    model_path: Path
    model_sha256: str
    model_revision: str
    max_boxes: int
    max_image_bytes: int
    default_pad: float
    default_otsu: bool
    source_url: str


def _int(name: str, default: int, minimum: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SettingsError(f"{name}={raw!r} is not an integer.") from exc
    if value < minimum:
        raise SettingsError(f"{name}={value} is below the minimum {minimum}.")
    return value


def _float(name: str, default: float, low: float, high: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise SettingsError(f"{name}={raw!r} is not a number.") from exc
    if not low <= value <= high:
        raise SettingsError(f"{name}={value} is outside [{low}, {high}].")
    return value


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    raise SettingsError(f"{name}={raw!r} is not a boolean.")


def load_settings() -> Settings:
    """Read the environment into :class:`Settings`, failing loudly."""
    api_key = os.environ.get("DDX_OMR_API_KEY", "").strip()
    if not api_key:
        raise SettingsError(
            "DDX_OMR_API_KEY is empty. The OMR service refuses to start without "
            "a key. Copy .env.example to .env and set one."
        )

    model_sha256 = os.environ.get("OMR_MODEL_SHA256", "").strip().lower()
    if len(model_sha256) != 64 or any(c not in "0123456789abcdef" for c in model_sha256):
        raise SettingsError(
            "OMR_MODEL_SHA256 must be the 64-hex SHA-256 of the weights file. "
            "The service refuses to load weights it cannot verify."
        )

    model_raw = Path(os.environ.get("OMR_MODEL_PATH", "").strip() or DEFAULT_MODEL_PATH)
    model_path = model_raw if model_raw.is_absolute() else SERVICE_ROOT / model_raw

    # AGPL-3.0 section 13: a network service must offer its source. No URL,
    # no start — an unannounced source offer is a licence breach, not a warning.
    source_url = os.environ.get("OMR_SOURCE_URL", "").strip()
    if not source_url:
        raise SettingsError(
            "OMR_SOURCE_URL is empty. The service must offer its AGPL source at "
            "GET /source; set the public repository URL in .env."
        )

    origins = tuple(
        part.strip() for part in os.environ.get("CORS_ORIGINS", "").split(",") if part.strip()
    )

    return Settings(
        app_name="ddx-omr-server",
        app_version=__version__,
        host=os.environ.get("HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=_int("OMR_PORT", 11513, 1),
        log_level=os.environ.get("LOG_LEVEL", "info").strip() or "info",
        api_key=api_key,
        cors_origins=origins,
        model_path=model_path,
        model_sha256=model_sha256,
        model_revision=os.environ.get("OMR_MODEL_REVISION", "").strip() or "unknown",
        max_boxes=_int("OMR_MAX_BOXES", 2000, 1),
        max_image_bytes=_int("OMR_MAX_IMAGE_BYTES", 25 * 1024 * 1024, 1024),
        default_pad=_float("OMR_DEFAULT_PAD", 0.35, 0.0, 2.0),
        default_otsu=_bool("OMR_DEFAULT_OTSU", True),
        source_url=source_url,
    )
