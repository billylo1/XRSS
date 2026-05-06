"""
Normalize User legacy payloads before twikit parses them — X omits keys twikit 2.3.3 assumes.

Also guards against applying this patch twice (would recurse User.__init__).
"""

from __future__ import annotations

_ORIG_USER_INIT = None
_PATCH_APPLIED = False


def _normalize_user_legacy(data: dict) -> None:
    """Mutate data['legacy'] in place with defaults twikit.User.__init__ expects."""
    legacy = data.get("legacy")
    if not isinstance(legacy, dict):
        return

    entities = legacy.get("entities")
    if not isinstance(entities, dict):
        entities = {}
        legacy["entities"] = entities

    desc = entities.get("description")
    if not isinstance(desc, dict):
        desc = {}
        entities["description"] = desc
    desc.setdefault("urls", [])

    legacy.setdefault("pinned_tweet_ids_str", [])
    legacy.setdefault("withheld_in_countries", [])


def apply_twikit_user_patch() -> None:
    global _ORIG_USER_INIT, _PATCH_APPLIED

    import twikit.user as user_module

    if _PATCH_APPLIED:
        return

    _ORIG_USER_INIT = user_module.User.__init__

    def __init__(self, client, data):  # type: ignore[no-untyped-def]
        if isinstance(data, dict):
            _normalize_user_legacy(data)
        _ORIG_USER_INIT(self, client, data)

    user_module.User.__init__ = __init__
    _PATCH_APPLIED = True
