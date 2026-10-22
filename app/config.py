"""Environment config and the single registry of model ids."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

NS_LIGHTNING_CLOUD = "nvidia/nemotron-3.5-lightning-30b-a3b"
NS_SUPER_VL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
NS_LOCAL_LANE = "nemotron-3-5-lightning-3-2"
LOCAL_RUNTIME_PREFIX = "local-runtime/"
LOCAL_RUNTIME_NEMOTRON_PREFIX = "local-runtime/nemotron"
NV_SUPER = "nvidia/nemotron-3.5-super-vl-120b-a12b"
NV_CONTENT_SAFETY = "nvidia/nemotron-3.5-content-safety"
NV_MODEL_ALIASES: dict[str, set[str]] = {
    NV_SUPER: {"private/nvidia/nemotron-3.5-super-120b-a12b"},
}


def allowed_served_models(requested: str) -> set[str]:
    return {requested, *NV_MODEL_ALIASES.get(requested, set())}


def is_local_runtime_id(model: str | None) -> bool:
    return bool(model) and model.startswith(LOCAL_RUNTIME_PREFIX)


def is_local_nemotron_lane(model: str | None) -> bool:
    """True for the local lane id or a local-runtime Nemotron model. Never cloud nvidia/ ids."""
    if not model or model.startswith("nvidia/"):
        return False
    if model == NS_LOCAL_LANE:
        return True
    return model.startswith(LOCAL_RUNTIME_NEMOTRON_PREFIX)


METERLESS_APP = "genai-nvidia"

_ENV_NAMES = (
    "METERLESS_BASE_URL",
    "METERLESS_RUNTIME_TOKEN",
    "NVIDIA_API_KEY",
    "ZETARIS_REST_URL",
    "ZETARIS_ORG_ID",
    "ZETARIS_API_KEY",
    "SAMPLE_MODE",
)

_SECRET_ENV_NAMES = (
    "METERLESS_RUNTIME_TOKEN",
    "NVIDIA_API_KEY",
    "ZETARIS_API_KEY",
)
_SECRET_MIN_LEN = 8


def getenv(name: str) -> str | None:
    """Return a trimmed env value, or None if unset/empty. Never log the value."""
    value = os.environ.get(name)
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def sample_mode() -> bool:
    raw = getenv("SAMPLE_MODE")
    if raw is None:
        return False
    return raw.lower() in {"1", "true", "yes", "on"}


def is_set(name: str) -> bool:
    return getenv(name) is not None


def describe() -> dict[str, str]:
    """Report which config variables are set. Never includes values."""
    return {name: ("set" if is_set(name) else "unset") for name in _ENV_NAMES}


def secret_values() -> list[str]:
    """Secret env values long enough to redact. Never log them."""
    found: list[str] = []
    for name in _SECRET_ENV_NAMES:
        value = getenv(name)
        if value is not None and len(value) >= _SECRET_MIN_LEN:
            found.append(value)
    return found
