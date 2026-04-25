"""
Favorites (pinned shortcuts) helpers for the Kodi integration.

Stores user-pinned directories/items in the per-device configuration so that
the user can jump directly to a deep-linked location (e.g. a YouTube channel
inside an addon, a Live TV channel, a sub-folder of a Source) from the
browse-media root.

:copyright: (c) 2026 by Albaintor
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import parse_qs, quote, urlencode

_LOG = logging.getLogger(__name__)

# Media-id prefixes used to encode favorites-related actions in the browse tree.
FAVORITES_ROOT = "kodi://favorites"
FAVORITES_MANAGE = "kodi://favorites/manage"
FAVORITES_TOGGLE_PREFIX = "kodi://favorites/toggle?"
FAVORITES_CLEANUP = "kodi://favorites/cleanup"


def normalize(entry: Any) -> dict | None:
    """Coerce a stored favorite into a fully-populated dict (defensive).

    Old configurations may contain entries missing some keys; we always
    return a dict with the canonical keys or ``None`` if unusable.
    """
    if not isinstance(entry, dict):
        return None
    media_id = entry.get("media_id")
    media_type = entry.get("media_type")
    if not media_id or not media_type:
        return None
    return {
        "media_id": str(media_id),
        "media_type": str(media_type),
        "title": str(entry.get("title") or media_id),
        "thumbnail": entry.get("thumbnail") or None,
        "broken": bool(entry.get("broken", False)),
    }


def list_favorites(raw: list | None) -> list[dict]:
    """Return a sanitized list of favorite entries."""
    if not raw:
        return []
    result: list[dict] = []
    for item in raw:
        norm = normalize(item)
        if norm is not None:
            result.append(norm)
    return result


def find_index(raw: list | None, media_id: str, media_type: str) -> int:
    """Return the index of a favorite by (media_id, media_type) or -1."""
    for idx, item in enumerate(list_favorites(raw)):
        if item["media_id"] == media_id and item["media_type"] == media_type:
            return idx
    return -1


def is_favorite(raw: list | None, media_id: str, media_type: str) -> bool:
    """Return True if (media_id, media_type) is currently pinned."""
    return find_index(raw, media_id, media_type) >= 0


def add(raw: list, media_id: str, media_type: str, title: str, thumbnail: str | None = None) -> bool:
    """Add a favorite if not already present. Returns True if added."""
    if find_index(raw, media_id, media_type) >= 0:
        return False
    raw.append(
        {
            "media_id": media_id,
            "media_type": media_type,
            "title": title or media_id,
            "thumbnail": thumbnail,
            "broken": False,
        }
    )
    return True


def remove(raw: list, media_id: str, media_type: str) -> bool:
    """Remove a favorite by (media_id, media_type). Returns True if removed."""
    idx = find_index(raw, media_id, media_type)
    if idx < 0:
        return False
    raw.pop(idx)
    return True


def remove_broken(raw: list) -> int:
    """Remove all entries flagged as broken. Returns number removed."""
    if not raw:
        return 0
    before = len(raw)
    raw[:] = [it for it in list_favorites(raw) if not it.get("broken")]
    return before - len(raw)


def mark_broken(raw: list, media_id: str, media_type: str, broken: bool = True) -> bool:
    """Flag (or unflag) a favorite as broken. Returns True if the flag changed."""
    items = list_favorites(raw)
    for idx, item in enumerate(items):
        if item["media_id"] == media_id and item["media_type"] == media_type:
            if bool(item.get("broken")) == broken:
                return False
            # Mutate in-place on the original list (which may contain partially populated entries).
            raw[idx] = {**item, "broken": broken}
            return True
    return False


def can_pin(media_id: str | None, media_type: str | None) -> bool:
    """Return True if a directory/item is eligible to be pinned.

    We deliberately limit pinning to URL-like targets that we know how to
    re-open later from the favorites root: addon plugin:// paths, PVR
    channel groups / channels, addon roots, and Kodi Sources sub-paths.
    Library-only nodes (e.g. ``kodi://videos/all``) are NOT pinnable yet
    because they are predefined entries.
    """
    # pylint: disable=R0911
    if not media_id:
        return False
    if media_id.startswith(FAVORITES_ROOT):
        return False
    if media_id.startswith("plugin://"):
        return True
    # Allow PVR channel group sub-listings and the channel groups page.
    if media_id.startswith("kodi://pvr/") and media_id != "kodi://pvr":
        return True
    # Allow Kodi Sources sub-paths (anything beneath kodi://sources/<root>).
    if media_id.startswith("kodi://sources/") and media_id.count("/") > 3:
        return True
    # Allow individual PVR channels / addons / channel groups by media_type.
    if media_type in ("channel", "channelgroup", "addon"):
        return True
    return False


def encode_toggle(media_id: str, media_type: str, title: str, parent: str | None = None) -> str:
    """Build the special media_id used by the pin/unpin toggle item."""
    qs = urlencode(
        {
            "id": media_id,
            "type": media_type,
            "title": title or media_id,
            "parent": parent or "",
        },
        quote_via=quote,
    )
    return FAVORITES_TOGGLE_PREFIX + qs


def decode_toggle(media_id: str) -> dict | None:
    """Parse a toggle media_id into its components, or return None."""
    if not media_id or not media_id.startswith(FAVORITES_TOGGLE_PREFIX):
        return None
    raw = media_id[len(FAVORITES_TOGGLE_PREFIX) :]
    parts = parse_qs(raw, keep_blank_values=True)

    def _first(key: str) -> str:
        values = parts.get(key) or [""]
        return values[0]

    target_id = _first("id")
    target_type = _first("type")
    if not target_id or not target_type:
        return None
    return {
        "media_id": target_id,
        "media_type": target_type,
        "title": _first("title") or target_id,
        "parent": _first("parent") or None,
    }
