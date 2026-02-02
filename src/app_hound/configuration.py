from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

CONFIG_FILE_NAME = "apps_config.json"


class ConfigurationError(RuntimeError):
    """Raised when an apps configuration file is malformed."""


@dataclass(frozen=True)
class AppConfiguration:
    """Represents configuration for a single application definition."""

    name: str
    additional_locations: tuple[Path, ...] = field(default_factory=tuple)
    installation_path: Path | None = None
    deep_home_search: bool = False
    patterns: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        base_dir: Path | None = None,
    ) -> AppConfiguration:
        """Create an :class:`AppConfiguration` from a JSON mapping."""
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigurationError(
                "Each app entry must include a non-empty 'name' string."
            )

        additional_locations = _normalise_path_tuple(
            raw.get("additional_locations"),
            base_dir=base_dir,
        )
        patterns = _normalise_string_tuple(raw.get("patterns"))
        installation_path = _normalise_optional_path(
            raw.get("installation_path"),
            base_dir=base_dir,
        )
        deep_home_search = raw.get("deep_home_search", False)
        if not isinstance(deep_home_search, bool):
            raise ConfigurationError("'deep_home_search' must be a boolean value.")

        return cls(
            name=name.strip(),
            additional_locations=additional_locations,
            installation_path=installation_path,
            deep_home_search=deep_home_search,
            patterns=patterns,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialise the configuration entry into a JSON-friendly dictionary."""
        return {
            "name": self.name,
            "additional_locations": [str(path) for path in self.additional_locations],
            "installation_path": str(self.installation_path)
            if self.installation_path
            else None,
            "deep_home_search": self.deep_home_search,
            "patterns": list(self.patterns),
        }


@dataclass(frozen=True)
class AppsConfiguration:
    """Container for all configured applications."""

    apps: tuple[AppConfiguration, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the configuration into a JSON-friendly dictionary."""
        return {"apps": [app.to_dict() for app in self.apps]}

    def app_names(self) -> tuple[str, ...]:
        """Return the configured application names."""
        return tuple(app.name for app in self.apps)


def default_config_path(root: Path | None = None) -> Path:
    """Return the default location for the configuration file."""
    base = root if root is not None else Path.cwd()
    return base / CONFIG_FILE_NAME


def load_configuration(path: str | Path) -> AppsConfiguration:
    """
    Load application configuration from a JSON file.

    The loader expands environment variables, supports optional fields, and raises
    :class:`ConfigurationError` when the schema is invalid.
    """
    config_path = Path(path).expanduser()
    if not config_path.exists():
        raise ConfigurationError(f"Configuration file not found: {config_path}")

    try:
        payload = _read_json(config_path)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            f"Invalid JSON in configuration file {config_path}"
        ) from exc

    apps_payload = payload.get("apps")
    if not isinstance(apps_payload, Sequence):
        raise ConfigurationError("Top-level 'apps' key must be a list of app entries.")

    apps: list[AppConfiguration] = []
    for index, entry in enumerate(apps_payload):
        if not isinstance(entry, Mapping):
            raise ConfigurationError(f"App entry at index {index} must be an object.")
        apps.append(AppConfiguration.from_mapping(entry, base_dir=config_path.parent))

    return AppsConfiguration(apps=tuple(apps))


def load_multiple_configurations(paths: Iterable[str | Path]) -> AppsConfiguration:
    """Load multiple configuration files and merge them into a single instance."""
    loaded = [load_configuration(path) for path in paths]
    return merge_configurations(loaded)


def merge_configurations(configs: Sequence[AppsConfiguration]) -> AppsConfiguration:
    """Merge multiple :class:`AppsConfiguration` objects."""
    merged_apps: list[AppConfiguration] = []
    for config in configs:
        merged_apps.extend(config.apps)
    return AppsConfiguration(apps=tuple(merged_apps))


def _read_json(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
        if not isinstance(data, Mapping):
            raise ConfigurationError("Configuration file must contain a JSON object.")
        return data


def _expand_env(value: str) -> str:
    return os.path.expanduser(os.path.expandvars(value))


def _normalise_path(value: str, *, base_dir: Path | None) -> Path:
    candidate = Path(_expand_env(value))
    if not candidate.is_absolute() and base_dir is not None:
        candidate = (base_dir / candidate).expanduser()
    return candidate


def _normalise_path_tuple(
    raw: Any,
    *,
    base_dir: Path | None,
) -> tuple[Path, ...]:
    if raw is None:
        return tuple()
    if isinstance(raw, (str, Path)):
        raw_values = [raw]
    elif isinstance(raw, Sequence):
        raw_values = list(raw)
    else:
        raise ConfigurationError(
            "'additional_locations' must be a string or list of strings."
        )
    paths: list[Path] = []
    for item in raw_values:
        if not isinstance(item, (str, Path)):
            raise ConfigurationError("Each additional location must be a string.")
        paths.append(_normalise_path(str(item), base_dir=base_dir))
    return tuple(paths)


def _normalise_optional_path(value: Any, *, base_dir: Path | None) -> Path | None:
    if value in (None, "", []):
        return None
    if not isinstance(value, (str, Path)):
        raise ConfigurationError("'installation_path' must be a string if provided.")
    return _normalise_path(str(value), base_dir=base_dir)


def _normalise_string_tuple(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return tuple()
    if isinstance(raw, str):
        return (raw,)
    if not isinstance(raw, Sequence):
        raise ConfigurationError("'patterns' must be a string or a list of strings.")
    cleaned: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise ConfigurationError("Each pattern must be a string.")
        if item.strip():
            cleaned.append(item.strip())
    return tuple(cleaned)


__all__ = [
    "CONFIG_FILE_NAME",
    "ConfigurationError",
    "AppConfiguration",
    "AppsConfiguration",
    "default_config_path",
    "load_configuration",
    "load_multiple_configurations",
    "merge_configurations",
]
