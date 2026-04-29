"""
Favorites helpers for the Kodi integration.

Provides a thin wrapper around Kodi's ``Favourites.GetFavourites`` JSON-RPC
endpoint so the media browser can display the user's Kodi-native favourites.

:copyright: (c) 2026 by Albaintor
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

from __future__ import annotations

import logging
from typing import Any

from const import IKodiDevice

_LOG = logging.getLogger(__name__)

# Media-id prefix for the virtual favourites browse root.
FAVORITES_ROOT = "kodi://favorites"

VALID_FAVOURITE_TYPES = frozenset({"media", "window", "script", "androidapp", "unknown"})


async def get_kodi_favourites(client: IKodiDevice) -> list[dict]:
    """Fetch the current favourites list from Kodi.

    Uses the ``get_favourites`` wrapper on the Kodi client which calls
    ``Favourites.GetFavourites``.  Returns the favourites array or an
    empty list on error so the browse UI can degrade gracefully.

    *client* must be a ``Kodi`` instance (i.e. ``device.client``), not the
    raw ``jsonrpc_base.Server``.
    """
    try:
        result = await client.get_favourites()
        return _extract_favourites(client, result)
    except Exception:  # pylint: disable=W0718
        _LOG.debug(
            "[%s] Failed to fetch Kodi favourites (method not available?)", client.device_config.address, exc_info=True
        )
        return []


def _extract_favourites(client: IKodiDevice, result: dict[str, Any]) -> list[dict]:
    """Validate and extract the favourites array from a GetFavourites result.

    Returns the favourites list, or an empty list when the response is
    malformed so callers can degrade gracefully.
    """
    if not isinstance(result, dict):
        _LOG.debug(
            "[%s] Favourites response: expected dict, got %s", client.device_config.address, type(result).__name__
        )
        return []

    favs = result.get("favourites")
    if favs is None:
        _LOG.debug("[%s] Favourites response missing 'favourites' key", client.device_config.address)
        return []
    if not isinstance(favs, list):
        _LOG.debug("[%s] 'favourites' must be an array, got %s", client.device_config.address, type(favs).__name__)
        return []

    limits = result.get("limits")
    if limits is not None:
        _validate_limits(client, limits)

    clean: list[dict] = []
    for idx, fav in enumerate(favs):
        if _validate_favourite(client, fav, idx):
            clean.append(fav)
    return clean


def _validate_favourite(client: IKodiDevice, fav: Any, index: int) -> bool:
    """Validate a single Favourite.Details.Favourite entry. Returns True if usable."""
    prefix = f"favourites[{index}]"
    if not isinstance(fav, dict):
        _LOG.debug("[%s] %s: expected object, got %s", client.device_config.address, prefix, type(fav).__name__)
        return False

    title = fav.get("title")
    if not isinstance(title, str) or not title:
        _LOG.debug("[%s] %s: missing or empty 'title'", client.device_config.address, prefix)
        return False

    fav_type = fav.get("type")
    if fav_type not in VALID_FAVOURITE_TYPES:
        _LOG.debug("[%s] %s: invalid type '%s'", client.device_config.address, prefix, fav_type)
        return False

    return True


def _validate_limits(client: IKodiDevice, limits: Any) -> None:
    """Log warnings for malformed List.LimitsReturned (non-fatal)."""
    if not isinstance(limits, dict):
        _LOG.debug("[%s] limits: expected object, got %s", client.device_config.address, type(limits).__name__)
        return
    total = limits.get("total")
    if not isinstance(total, int) or total < 0:
        _LOG.debug("[%s] limits: 'total' should be a non-negative int, got %r", client.device_config.address, total)
