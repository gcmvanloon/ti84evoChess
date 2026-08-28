"""Configuration front end for the AST feature-selection pass.

This module owns the build-profile schema, strict JSON loading, validation,
and resolution. Its public boundary with ``ast_preprocessor.py`` is
``ResolvedProfile``: the CLI loads one profile here, then passes that resolved
value into ``SelectBuildFeaturesPass``. This module does not parse or transform
calculator source code.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


PROFILE_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
PIECE_STYLES = frozenset(("graphical", "glyphs"))
BOOLEAN_FEATURES = (
    "capture_panel",
    "material_counter",
    "move_counter",
    "player_undo",
)
DEBUG_METRICS = (
    "last_key",
    "free_memory",
    "ai_time",
    "ai_evaluated_moves",
)
FEATURE_NAMES = frozenset(
    BOOLEAN_FEATURES
    + ("debug_panel",)
    + tuple("debug_panel.metrics." + name for name in DEBUG_METRICS)
)
CHOICES = {"piece_style": PIECE_STYLES}


class ProfileError(ValueError):
    """Raised when build profile configuration is invalid."""


@dataclass(frozen=True)
class ProfileDocument:
    default_profile: str
    profiles: dict[str, Any]


@dataclass(frozen=True)
class ResolvedProfile:
    """Validated, fully resolved input to ``SelectBuildFeaturesPass``."""

    name: str
    piece_style: str
    features: dict[str, bool]

    @property
    def enabled_features(self) -> tuple[str, ...]:
        return tuple(name for name in sorted(self.features) if self.features[name])


class _ObjectPairs(list[tuple[str, Any]]):
    pass


def _object_pairs(pairs: list[tuple[str, Any]]) -> _ObjectPairs:
    return _ObjectPairs(pairs)


def _convert_json(value: Any, path: str) -> Any:
    if isinstance(value, _ObjectPairs):
        result: dict[str, Any] = {}
        for key, item in value:
            property_path = f"{path}.{key}"
            if key in result:
                raise _error(property_path, "duplicate object key")
            result[key] = _convert_json(item, property_path)
        return result
    if isinstance(value, list):
        return [_convert_json(item, f"{path}[{index}]") for index, item in enumerate(value)]
    return value


def _error(path: str, message: str) -> ProfileError:
    return ProfileError(f"{path}: {message}")


def _require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error(path, "must be a JSON object")
    return value


def _reject_unknown(value: dict[str, Any], allowed: set[str], path: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise _error(f"{path}.{unknown[0]}", "unknown property")


def parse_profile_document(contents: str, filename: str = "build_profiles.json") -> ProfileDocument:
    try:
        value = _convert_json(
            json.loads(contents, object_pairs_hook=_object_pairs), "root"
        )
    except json.JSONDecodeError as error:
        raise ProfileError(
            f"{filename}:{error.lineno}:{error.colno}: {error.msg}"
        ) from error
    root = _require_object(value, "root")
    _reject_unknown(root, {"default_profile", "profiles"}, "root")

    if "default_profile" not in root:
        raise _error("root.default_profile", "is required")
    default_profile = root["default_profile"]
    if not isinstance(default_profile, str):
        raise _error("root.default_profile", "must be a string")

    if "profiles" not in root:
        raise _error("root.profiles", "is required")
    profiles = _require_object(root["profiles"], "root.profiles")
    if not profiles:
        raise _error("root.profiles", "must not be empty")
    for name in profiles:
        if not PROFILE_NAME.fullmatch(name):
            raise _error(
                f"root.profiles.{name}",
                "profile name must contain only lowercase ASCII letters, digits, underscores, or hyphens",
            )
    if default_profile not in profiles:
        raise _error("root.default_profile", f"names unknown profile {default_profile!r}")
    return ProfileDocument(default_profile, profiles)


def load_profile_document(path: Path) -> ProfileDocument:
    try:
        contents = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ProfileError(f"could not read {path}: {error}") from error
    return parse_profile_document(contents, str(path))


def _boolean(value: Any, path: str) -> bool:
    if type(value) is not bool:
        raise _error(path, "must be a JSON Boolean")
    return value


def resolve_profile(document: ProfileDocument, name: str | None = None) -> ResolvedProfile:
    selected = document.default_profile if name is None else name
    if selected not in document.profiles:
        raise _error("profile", f"unknown profile {selected!r}")
    path = f"root.profiles.{selected}"
    profile = _require_object(document.profiles[selected], path)
    _reject_unknown(profile, {"piece_style", "features"}, path)

    if "piece_style" not in profile:
        raise _error(f"{path}.piece_style", "is required")
    piece_style = profile["piece_style"]
    if not isinstance(piece_style, str) or piece_style not in PIECE_STYLES:
        raise _error(
            f"{path}.piece_style",
            "must be one of " + ", ".join(repr(value) for value in sorted(PIECE_STYLES)),
        )

    features_value = profile.get("features", {})
    features = _require_object(features_value, f"{path}.features")
    allowed_features = set(BOOLEAN_FEATURES) | {"debug_panel"}
    _reject_unknown(features, allowed_features, f"{path}.features")

    resolved = {name: False for name in FEATURE_NAMES}
    for feature in BOOLEAN_FEATURES:
        if feature in features:
            resolved[feature] = _boolean(
                features[feature], f"{path}.features.{feature}"
            )

    debug_value = features.get("debug_panel", {})
    debug = _require_object(debug_value, f"{path}.features.debug_panel")
    _reject_unknown(debug, {"metrics"}, f"{path}.features.debug_panel")
    metrics_value = debug.get("metrics", {})
    metrics = _require_object(
        metrics_value, f"{path}.features.debug_panel.metrics"
    )
    _reject_unknown(metrics, set(DEBUG_METRICS), f"{path}.features.debug_panel.metrics")
    for metric in DEBUG_METRICS:
        dotted = "debug_panel.metrics." + metric
        if metric in metrics:
            resolved[dotted] = _boolean(
                metrics[metric], f"{path}.features.debug_panel.metrics.{metric}"
            )
    resolved["debug_panel"] = any(
        resolved["debug_panel.metrics." + metric] for metric in DEBUG_METRICS
    )
    return ResolvedProfile(selected, piece_style, resolved)


def load_resolved_profile(path: Path, name: str | None = None) -> ResolvedProfile:
    """Load configuration and return the selection consumed by the AST pass."""

    return resolve_profile(load_profile_document(path), name)


def metrics_filename(profile_name: str) -> str:
    return "BUILD_METRICS_" + profile_name.upper().replace("-", "_") + ".csv"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--list-profiles", action="store_true")
    parser.add_argument("--profile")
    arguments = parser.parse_args()
    if arguments.list_profiles and arguments.profile:
        parser.error("--list-profiles and --profile cannot be combined")
    document = load_profile_document(arguments.config)
    if arguments.list_profiles:
        for name in sorted(document.profiles):
            resolve_profile(document, name)
            print(name)
    elif arguments.profile:
        print(resolve_profile(document, arguments.profile).name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
