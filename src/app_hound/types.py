from typing import TypedDict, TypeGuard, Any, NotRequired


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
    additional_locations: list[str]
    installation_path: NotRequired[str | None]


class AppsConfig(TypedDict):
    apps: list[AppConfigEntry]


def is_app_config_entry(obj: Any) -> TypeGuard[AppConfigEntry]:  # pyright: ignore[reportExplicitAny, reportAny]
    if not isinstance(obj, dict):
        return False
    if "name" not in obj or not isinstance(obj["name"], str):
        return False
    if "additional_locations" not in obj or not isinstance(
        obj["additional_locations"], list
    ):
        return False
    if not all(isinstance(loc, str) for loc in obj["additional_locations"]):  # pyright: ignore[reportUnknownVariableType]
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
