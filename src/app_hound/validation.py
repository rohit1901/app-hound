"""Input validation for CLI arguments and configuration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class ValidationError(ValueError):
    """Raised when input validation fails."""

    pass


def validate_app_name(name: str | None) -> str:
    """
    Validate application name.

    Args:
        name: Application name to validate

    Returns:
        Validated and cleaned app name

    Raises:
        ValidationError: If name is invalid
    """
    if not name:
        raise ValidationError("Application name cannot be empty")

    if not isinstance(name, str):
        raise ValidationError(f"Application name must be a string, got {type(name)}")

    cleaned = name.strip()
    if not cleaned:
        raise ValidationError("Application name cannot be only whitespace")

    if len(cleaned) > 255:
        raise ValidationError("Application name is too long (max 255 characters)")

    # Check for path traversal attempts
    if ".." in cleaned or "/" in cleaned or "\\" in cleaned:
        raise ValidationError(
            "Application name cannot contain path separators or '..' sequences"
        )

    return cleaned


def validate_file_path(
    path: str | Path | None,
    *,
    must_exist: bool = False,
    must_be_file: bool = False,
    must_be_dir: bool = False,
    allow_none: bool = False,
) -> Path | None:
    """
    Validate a file or directory path.

    Args:
        path: Path to validate
        must_exist: If True, path must exist
        must_be_file: If True, path must be a file
        must_be_dir: If True, path must be a directory
        allow_none: If True, None is acceptable

    Returns:
        Validated Path object or None

    Raises:
        ValidationError: If validation fails
    """
    if path is None:
        if allow_none:
            return None
        raise ValidationError("Path cannot be None")

    if not isinstance(path, (str, Path)):
        raise ValidationError(f"Path must be string or Path, got {type(path)}")

    try:
        path_obj = Path(path).expanduser()
    except (ValueError, RuntimeError) as exc:
        raise ValidationError(f"Invalid path '{path}': {exc}") from exc

    # Resolve to absolute path for security
    try:
        resolved = path_obj.resolve()
    except (OSError, RuntimeError):
        # If resolution fails, use the expanded path
        resolved = path_obj

    if must_exist and not resolved.exists():
        raise ValidationError(f"Path does not exist: {resolved}")

    if must_be_file and resolved.exists() and not resolved.is_file():
        raise ValidationError(f"Path is not a file: {resolved}")

    if must_be_dir and resolved.exists() and not resolved.is_dir():
        raise ValidationError(f"Path is not a directory: {resolved}")

    return resolved


def validate_glob_pattern(pattern: str) -> str:
    """
    Validate a glob pattern.

    Args:
        pattern: Glob pattern to validate

    Returns:
        Validated pattern

    Raises:
        ValidationError: If pattern is invalid
    """
    if not pattern:
        raise ValidationError("Glob pattern cannot be empty")

    if not isinstance(pattern, str):
        raise ValidationError(f"Glob pattern must be a string, got {type(pattern)}")

    cleaned = pattern.strip()
    if not cleaned:
        raise ValidationError("Glob pattern cannot be only whitespace")

    # Expand user home directory
    cleaned = cleaned.replace("~", str(Path.home()))

    # Check for dangerous patterns
    if cleaned.startswith("/") and ".." in cleaned:
        raise ValidationError(
            "Glob pattern contains potentially dangerous path traversal"
        )

    return cleaned


def validate_color(color: str | None, *, allow_none: bool = True) -> str | None:
    """
    Validate a color string for Rich formatting.

    Args:
        color: Color string to validate (e.g., "red", "bright_blue", "#ff0000")
        allow_none: If True, None is acceptable

    Returns:
        Validated color string or None

    Raises:
        ValidationError: If color is invalid
    """
    if color is None:
        if allow_none:
            return None
        raise ValidationError("Color cannot be None")

    if not isinstance(color, str):
        raise ValidationError(f"Color must be a string, got {type(color)}")

    cleaned = color.strip().lower()
    if not cleaned:
        if allow_none:
            return None
        raise ValidationError("Color cannot be empty or whitespace")

    # Valid Rich color formats:
    # - Named colors: "red", "green", "blue", etc.
    # - Bright colors: "bright_red", "bright_green", etc.
    # - Hex colors: "#ff0000", "#f00"
    # - RGB: "rgb(255,0,0)"

    # Hex color validation
    if cleaned.startswith("#"):
        hex_pattern = re.compile(r"^#([0-9a-f]{3}|[0-9a-f]{6})$")
        if not hex_pattern.match(cleaned):
            raise ValidationError(
                f"Invalid hex color '{color}'. Use #RGB or #RRGGBB format"
            )
        return cleaned

    # RGB color validation
    if cleaned.startswith("rgb(") and cleaned.endswith(")"):
        rgb_content = cleaned[4:-1]
        parts = [p.strip() for p in rgb_content.split(",")]
        if len(parts) != 3:
            raise ValidationError(f"Invalid RGB color '{color}'. Use rgb(r,g,b) format")
        try:
            values = [int(p) for p in parts]
            if not all(0 <= v <= 255 for v in values):
                raise ValidationError(f"RGB values must be between 0-255 in '{color}'")
        except ValueError:
            raise ValidationError(f"Invalid RGB values in '{color}'")
        return cleaned

    # Named color validation (basic check)
    # Rich supports many colors, we'll allow alphanumeric with underscores
    name_pattern = re.compile(r"^[a-z0-9_]+$")
    if not name_pattern.match(cleaned):
        raise ValidationError(
            f"Invalid color name '{color}'. Use named colors, hex (#RGB), or rgb(r,g,b)"
        )

    return cleaned


def validate_log_level(level: str | None) -> str | None:
    """
    Validate logging level.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Validated uppercase log level

    Raises:
        ValidationError: If level is invalid
    """
    if level is None:
        return None

    if not isinstance(level, str):
        raise ValidationError(f"Log level must be a string, got {type(level)}")

    cleaned = level.strip().upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

    if cleaned not in valid_levels:
        raise ValidationError(
            f"Invalid log level '{level}'. Must be one of: {', '.join(sorted(valid_levels))}"
        )

    return cleaned


def validate_config_paths(paths: str) -> list[Path]:
    """
    Validate and parse comma-separated configuration file paths.

    Args:
        paths: Comma-separated paths string

    Returns:
        List of validated Path objects

    Raises:
        ValidationError: If any path is invalid
    """
    if not paths:
        raise ValidationError("Configuration paths cannot be empty")

    if not isinstance(paths, str):
        raise ValidationError(f"Paths must be a string, got {type(paths)}")

    path_list = [p.strip() for p in paths.split(",") if p.strip()]

    if not path_list:
        raise ValidationError("No valid paths found in input")

    validated = []
    for path_str in path_list:
        try:
            path = validate_file_path(path_str, must_exist=True)
            if path:
                validated.append(path)
        except ValidationError as exc:
            raise ValidationError(f"Invalid path '{path_str}': {exc}") from exc

    return validated


def validate_positive_integer(
    value: Any, *, name: str = "value", min_value: int = 1
) -> int:
    """
    Validate a positive integer.

    Args:
        value: Value to validate
        name: Name of the value for error messages
        min_value: Minimum acceptable value

    Returns:
        Validated integer

    Raises:
        ValidationError: If value is invalid
    """
    if not isinstance(value, int):
        try:
            value = int(value)
        except (ValueError, TypeError) as exc:
            raise ValidationError(
                f"{name} must be an integer, got {type(value)}"
            ) from exc

    if value < min_value:
        raise ValidationError(f"{name} must be at least {min_value}, got {value}")

    return value


def validate_json_path(path: str | Path) -> Path:
    """
    Validate a JSON file path.

    Args:
        path: Path to JSON file

    Returns:
        Validated Path object

    Raises:
        ValidationError: If path is invalid or not a JSON file
    """
    validated_path = validate_file_path(path)
    if validated_path is None:
        raise ValidationError("JSON path cannot be None")

    if validated_path.suffix.lower() not in {".json"}:
        raise ValidationError(
            f"File must have .json extension, got: {validated_path.suffix}"
        )

    return validated_path


def sanitize_input(value: str, *, max_length: int = 1000) -> str:
    """
    Sanitize user input to prevent injection attacks.

    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string

    Raises:
        ValidationError: If input is dangerous
    """
    if not isinstance(value, str):
        raise ValidationError(f"Input must be a string, got {type(value)}")

    if len(value) > max_length:
        raise ValidationError(f"Input too long (max {max_length} characters)")

    # Check for null bytes
    if "\x00" in value:
        raise ValidationError("Input contains null bytes")

    # Check for control characters (except common whitespace)
    if any(ord(c) < 32 and c not in "\t\n\r" for c in value):
        raise ValidationError("Input contains control characters")

    return value


__all__ = [
    "ValidationError",
    "validate_app_name",
    "validate_file_path",
    "validate_glob_pattern",
    "validate_color",
    "validate_log_level",
    "validate_config_paths",
    "validate_positive_integer",
    "validate_json_path",
    "sanitize_input",
]
