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

_LOG = logging.getLogger(__name__)

# Media-id prefix for the virtual favourites browse root.
FAVORITES_ROOT = "kodi://favorites"


async def get_kodi_favourites(server: Any) -> list[dict]:
    """Fetch the current favourites list from Kodi.

    Uses the ``get_favourites`` wrapper on the Kodi client which calls
    ``Favourites.GetFavourites``.  Returns the favourites array or an
    empty list on error so the browse UI can degrade gracefully.
    """
    try:
        result = await server.get_favourites()
        return result.get("favourites", [])
    except Exception:
        _LOG.warning("Failed to fetch Kodi favourites", exc_info=True)
        return []
