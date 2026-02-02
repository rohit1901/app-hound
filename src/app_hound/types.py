from typing import Any, NotRequired, TypedDict, TypeGuard


# types for apps_config
# {
#   "apps": [
#     {
#       "name": "PDF Expert",
#       "additional_locations": ["/opt/pdf-expert", "/usr/local/share/pdfexpert"]
#     },
#     {
#       "name": "Spotify",
#       "additional_locations": ["/opt/spotify", "/usr/local/share/spotify"]
#     }
#   ]
# }
class AppConfigEntry(TypedDict):
    name: str
    additional_locations: NotRequired[list[str]]
    installation_path: NotRequired[str | None]
    deep_home_search: NotRequired[bool]
    patterns: NotRequired[list[str]]


class AppsConfig(TypedDict):
    apps: list[AppConfigEntry]


def is_app_config_entry(obj: Any) -> TypeGuard[AppConfigEntry]:  # pyright: ignore[reportExplicitAny, reportAny]
    if not isinstance(obj, dict):
        return False
    name = obj.get("name")
    if not isinstance(name, str) or not name.strip():
        return False
    if "additional_locations" in obj:
        additional = obj["additional_locations"]
        if not isinstance(additional, list):
            return False
        if not all(isinstance(location, str) for location in additional):  # pyright: ignore[reportUnknownVariableType]
            return False
    if "installation_path" in obj:
        installation = obj["installation_path"]
        if installation is not None and not isinstance(installation, str):
            return False
    if "deep_home_search" in obj and not isinstance(obj["deep_home_search"], bool):
        return False
    if "patterns" in obj:
        patterns = obj["patterns"]
        if not isinstance(patterns, list):
            return False
        if not all(isinstance(pattern, str) for pattern in patterns):  # pyright: ignore[reportUnknownVariableType]
            return False
    return True


def is_apps_config(obj: Any) -> TypeGuard[AppsConfig]:  # pyright: ignore[reportExplicitAny, reportAny]
    if not isinstance(obj, dict):
        return False
    if "apps" not in obj or not isinstance(obj["apps"], list):
        return False
    if not all(is_app_config_entry(app) for app in obj["apps"]):  # pyright: ignore[reportUnknownVariableType]
        return False
    return True
