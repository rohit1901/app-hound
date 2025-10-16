import pytest

from typing import Any
from app_hound.types import (  # Replace with actual module name
    AppConfigEntry,
    AppsConfig,
    is_app_config_entry,
    is_apps_config,
)


# --- AppConfigEntry type guard tests ---
def test_is_app_config_entry_valid():
    valid_entry: AppConfigEntry = {
        "name": "TestApp",
        "additional_locations": ["/opt/test", "/usr/local/test"],
    }
    assert is_app_config_entry(valid_entry) is True


def test_is_app_config_entry_missing_name():
    entry: Any = {"additional_locations": ["/opt/test"]}  # pyright: ignore[reportExplicitAny]
    assert is_app_config_entry(entry) is False


def test_is_app_config_entry_name_not_str():
    entry: Any = {  # pyright: ignore[reportExplicitAny]
        "name": 123,  # not str
        "additional_locations": ["/opt/test"],
    }
    assert is_app_config_entry(entry) is False


def test_is_app_config_entry_missing_additional_locations():
    entry: Any = {"name": "TestApp"}  # pyright: ignore[reportExplicitAny]
    assert is_app_config_entry(entry) is False


def test_is_app_config_entry_additional_locations_not_list():
    entry: Any = {"name": "TestApp", "additional_locations": "not_a_list"}  # pyright: ignore[reportExplicitAny]
    assert is_app_config_entry(entry) is False


def test_is_app_config_entry_additional_locations_list_not_str():
    entry: Any = {"name": "TestApp", "additional_locations": [123, None]}  # pyright: ignore[reportExplicitAny]
    assert is_app_config_entry(entry) is False


def test_is_app_config_entry_not_dict():
    entry: Any = ["name", "TestApp", "additional_locations"]  # pyright: ignore[reportExplicitAny]
    assert is_app_config_entry(entry) is False


# --- AppsConfig type guard tests ---
def test_is_apps_config_valid():
    valid_config: AppsConfig = {
        "apps": [
            {"name": "PDF Expert", "additional_locations": ["/opt/pdf-expert"]},
            {"name": "Spotify", "additional_locations": ["/opt/spotify"]},
        ]
    }
    assert is_apps_config(valid_config) is True


def test_is_apps_config_not_dict():
    config: Any = ["apps", []]  # pyright: ignore[reportExplicitAny]
    assert is_apps_config(config) is False


def test_is_apps_config_missing_apps():
    config: Any = {"not_apps": []}  # pyright: ignore[reportExplicitAny]
    assert is_apps_config(config) is False


def test_is_apps_config_apps_not_list():
    config: Any = {"apps": "not_a_list"}  # pyright: ignore[reportExplicitAny]
    assert is_apps_config(config) is False


def test_is_apps_config_apps_list_with_invalid_entry():
    config: Any = {  # pyright: ignore[reportExplicitAny]
        "apps": [
            {"name": "PDF Expert"},  # missing additional_locations
            {"name": "Spotify", "additional_locations": ["/opt/spotify"]},
        ]
    }
    assert is_apps_config(config) is False


def test_is_apps_config_apps_list_elem_not_dict():
    config: Any = {  # pyright: ignore[reportExplicitAny]
        "apps": [
            "not_a_dict",
            {"name": "Spotify", "additional_locations": ["/opt/spotify"]},
        ]
    }
    assert is_apps_config(config) is False
