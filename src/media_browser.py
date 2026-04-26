"""
Browsing definitions used for Kodi integration.

:copyright: (c) 2026 by Albaintor
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import dataclasses
import logging
import os
import re
import time
from dataclasses import dataclass, field, fields
from typing import Any
from urllib.parse import quote, unquote

from ucapi import StatusCodes
from ucapi.media_player import (
    BrowseMediaItem,
    MediaClass,
    MediaContentType,
    SearchMediaFilter,
)

import config
import favorites
from const import (
    IKodiDevice,
    KodiMediaTypes,
    KodiObjectType,
    PaginationOptions,
)
from translations import TRANSLATIONS

_LOG = logging.getLogger(__name__)

# pylint: disable=C0302,R0801,R0917,W1405

# ucapi BrowseMediaItem.media_id is hard-capped at 255 characters.
# Some Kodi addons (e.g. plugin.video.twitch followed channels) emit child
# entries whose 'file' URL exceeds that limit. We must filter them out at
# the construction sites or the BrowseMediaItem constructor raises
# ValueError mid-loop and aborts the whole listing.
MAX_MEDIA_ID_LEN = 255


MEDIA_CONTENT_LABELS = {
    MediaContentType.MOVIE: "Videos",
    MediaContentType.TV_SHOW: "TV Shows",
    MediaContentType.ALBUM: "Albums",
    MediaContentType.ARTIST: "Artists",
    MediaContentType.MUSIC: "Music",
}


@dataclass
class Paging:
    """Browsing paging."""

    page: int = field(default=1)
    limit: int = field(default=10)
    count: int | None = field(default=None)

    def __post_init__(self):
        """Apply default values on missing fields."""
        for attribute in fields(self):
            # If there is a default and the value of the field is none we can assign a value
            if (
                not isinstance(attribute.default, dataclasses.MISSING.__class__)
                and getattr(self, attribute.name) is None
            ):
                setattr(self, attribute.name, attribute.default)


SOURCE_MEDIA_TYPES_MAPPING = {
    "kodi://sources/videos": KodiMediaTypes.VIDEOS,
    "kodi://sources/music": KodiMediaTypes.MUSIC,
    "kodi://sources/pictures": KodiMediaTypes.PICTURES,
    "kodi://sources/files": KodiMediaTypes.FILES,
    "kodi://sources/programs": KodiMediaTypes.PROGRAMS,
}


def get_artwork(artworks: dict[str, str] | None) -> str | None:
    """Return best available artwork."""
    if artworks is None:
        return None
    return artworks.get(
        "poster",
        artworks.get("fanart", artworks.get("album.thumb", artworks.get("thumb", None))),
    )


def get_element(element: Any | None) -> str | None:
    """Return best available element."""
    if element is None:
        return None
    if isinstance(element, list):
        return element[0] if len(element) > 0 else None
    return element


# Kodi BBCode-style formatting tags used by skins/addons in labels.
# Examples: [B]bold[/B], [I]italic[/I], [COLOR red]x[/COLOR], [CR], [LIGHT], [UPPERCASE]...
_KODI_BBCODE_RE = re.compile(
    r"\[/?(?:B|I|U|S|CR|LIGHT|UPPERCASE|LOWERCASE|CAPITALIZE|COLOR(?:\s+[^\]]*)?|FONT(?:\s+[^\]]*)?)\]",
    re.IGNORECASE,
)


def strip_kodi_formatting(value: str | None) -> str:
    """Remove Kodi BBCode-style formatting tags from a label."""
    if not value:
        return value or ""
    cleaned = _KODI_BBCODE_RE.sub("", value)
    # Collapse whitespace introduced by removed tags
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


EPISODE_PROPERTIES = [
    "art",
    "file",
    "resume",
    "runtime",
    "showtitle",
    "season",
    "episode",
    "rating",
    "playcount",
]
MOVIE_PROPERTIES = ["resume", "art", "runtime", "rating", "year", "playcount"]


class MediaBrowser:
    """Media browser."""

    def __init__(self, device: IKodiDevice):
        """Initialize media browser instance."""
        self._device = device
        self._back_support = False
        if self._back_support:
            self._library_items = KODI_BROWSING_BACK + KODI_BROWSING
        else:
            self._library_items = KODI_BROWSING
        # Cached availability of optional Kodi features (None = not yet probed)
        self._pvr_available: bool | None = None
        self._addons_video_available: bool | None = None
        self._addons_audio_available: bool | None = None

    async def _is_pvr_available(self) -> bool:
        """Return True if Kodi has at least one PVR channel group (TV or Radio)."""
        if self._pvr_available is not None:
            return self._pvr_available
        try:
            for ctype in ("tv", "radio"):
                groups = await self._device.server.PVR.GetChannelGroups(channeltype=ctype)
                if (groups or {}).get("channelgroups"):
                    self._pvr_available = True
                    return True
            self._pvr_available = False
        # pylint: disable=W0718
        except Exception:
            self._pvr_available = False
        return self._pvr_available

    async def _is_addons_available(self, content: str) -> bool:
        """Return True if Kodi has at least one addon for the given content type."""
        cache_attr = "_addons_video_available" if content == "video" else "_addons_audio_available"
        cached = getattr(self, cache_attr)
        if cached is not None:
            return cached
        try:
            result = await self._device.server.Addons.GetAddons(
                content=content, enabled=True, limits={"start": 0, "end": 1}
            )
            available = bool((result or {}).get("addons"))
        # pylint: disable=W0718
        except Exception:
            available = False
        setattr(self, cache_attr, available)
        return available

    async def _filter_optional_roots(self, items: list[BrowseMediaItem]) -> list[BrowseMediaItem]:
        """Hide PVR/Addons roots and sub-roots if Kodi has nothing to show."""
        result: list[BrowseMediaItem] = []
        for it in items:
            mid = it.media_id
            if mid == "kodi://pvr":
                if not await self._is_pvr_available():
                    continue
            elif mid == "kodi://addons":
                if not (await self._is_addons_available("video") or await self._is_addons_available("audio")):
                    continue
            elif mid == "kodi://addons/video":
                if not await self._is_addons_available("video"):
                    continue
            elif mid == "kodi://addons/audio":
                if not await self._is_addons_available("audio"):
                    continue
            elif mid == "kodi://favorites":
                if not favorites.list_favorites(self._device.device_config.favorites):
                    continue
            result.append(it)
        return result

    # ---------------------------------------------------------------- favorites
    def _persist_favorites(self) -> None:
        """Persist the current device configuration after a favorites change."""
        try:
            if config.devices is not None:
                config.devices.update(self._device.device_config)
        # pylint: disable=W0718
        except Exception as ex:
            _LOG.warning(
                "[%s] Could not persist favorites: %s",
                self._device.device_config.address,
                ex,
            )

    def _favorite_item(self, fav: dict, *, with_unpin: bool = False) -> BrowseMediaItem | None:
        """Render a saved favorite as a BrowseMediaItem.

        When ``with_unpin`` is True, the returned item itself toggles (unpins)
        the favorite on click; this is used in the management view so dead
        favorites can still be removed without navigating into them.

        Returns None when the resulting media_id would exceed the ucapi
        255-char cap (would otherwise crash the whole browse listing).
        """
        title = fav.get("title") or fav.get("media_id", "")
        if fav.get("broken"):
            title = f"⚠ {title}"
        if with_unpin:
            toggle_id = favorites.encode_toggle(
                fav["media_id"], fav["media_type"], fav.get("title", title), favorites.FAVORITES_MANAGE
            )
            if len(toggle_id) > MAX_MEDIA_ID_LEN:
                _LOG.warning(
                    "Skipping unpin item, toggle media_id exceeds %d chars for %s",
                    MAX_MEDIA_ID_LEN,
                    str(fav.get("media_id", ""))[:120],
                )
                return None
            return BrowseMediaItem(
                title=self.get_localized("Unpin") + ": " + title,
                media_id=toggle_id,
                media_class=MediaClass.DIRECTORY,
                media_type=MediaContentType.URL.value,
                can_browse=True,
                can_play=False,
                thumbnail=fav.get("thumbnail"),
                items=[],
            )
        # Normal favorite: keep the original media_id/media_type so the
        # standard browse/play handlers do the work. We still wrap browsing
        # in a try/except later so that broken plugin:// targets do not
        # leave the user stuck.
        media_id = fav["media_id"]
        media_type = fav["media_type"]
        if len(media_id) > MAX_MEDIA_ID_LEN:
            _LOG.warning(
                "Skipping favorite, media_id exceeds %d chars: %s",
                MAX_MEDIA_ID_LEN,
                media_id[:120],
            )
            return None
        can_play = media_type in ("channel",) or media_id.startswith("plugin://") and "?" in media_id
        return BrowseMediaItem(
            title=title,
            media_id=media_id,
            media_class=MediaClass.DIRECTORY,
            media_type=media_type,
            can_browse=True,
            can_play=can_play,
            thumbnail=fav.get("thumbnail"),
            items=[],
        )

    def _build_favorites_root(self, paging: PaginationOptions) -> tuple[BrowseMediaItem, PaginationOptions]:
        """Render the ``kodi://favorites`` root listing."""
        item = self.get_root_item()
        item.media_id = favorites.FAVORITES_ROOT
        item.title = self.get_localized("Favorites")
        favs = favorites.list_favorites(self._device.device_config.favorites)
        sub: list[BrowseMediaItem] = [self.get_back_item("kodi://")]
        for fav in favs:
            entry = self._favorite_item(fav)
            if entry is not None:
                sub.append(entry)
        if favs:
            sub.append(
                BrowseMediaItem(
                    title=self.get_localized("Manage favorites"),
                    media_id=favorites.FAVORITES_MANAGE,
                    media_class=MediaClass.DIRECTORY,
                    media_type=MediaContentType.URL.value,
                    can_browse=True,
                    can_play=False,
                    items=[],
                )
            )
        item.items = sub
        paging.count = len(sub)
        return item, paging

    def _build_favorites_manage(self, paging: PaginationOptions) -> tuple[BrowseMediaItem, PaginationOptions]:
        """Render the management view (one toggle entry per favorite + cleanup)."""
        item = self.get_root_item()
        item.media_id = favorites.FAVORITES_MANAGE
        item.title = self.get_localized("Manage favorites")
        favs = favorites.list_favorites(self._device.device_config.favorites)
        sub: list[BrowseMediaItem] = [self.get_back_item(favorites.FAVORITES_ROOT)]
        for fav in favs:
            entry = self._favorite_item(fav, with_unpin=True)
            if entry is not None:
                sub.append(entry)
        if any(f.get("broken") for f in favs):
            sub.append(
                BrowseMediaItem(
                    title=self.get_localized("Cleanup broken favorites"),
                    media_id=favorites.FAVORITES_CLEANUP,
                    media_class=MediaClass.DIRECTORY,
                    media_type=MediaContentType.URL.value,
                    can_browse=True,
                    can_play=False,
                    items=[],
                )
            )
        item.items = sub
        paging.count = len(sub)
        return item, paging

    def _build_confirmation(
        self, message: str, parent_id: str, paging: PaginationOptions
    ) -> tuple[BrowseMediaItem, PaginationOptions]:
        """Build a tiny browse view used as feedback after a favorites action."""
        item = self.get_root_item()
        item.media_id = parent_id
        item.title = message
        item.items = [self.get_back_item(parent_id)]
        paging.count = 1
        return item, paging

    def _handle_favorites_toggle(
        self, media_id: str, paging: PaginationOptions
    ) -> tuple[BrowseMediaItem, PaginationOptions]:
        """Add or remove a favorite based on a toggle media_id."""
        params = favorites.decode_toggle(media_id)
        if not params:
            return self._build_confirmation(self.get_localized("Invalid favorite"), favorites.FAVORITES_ROOT, paging)
        cfg = self._device.device_config
        if cfg.favorites is None:
            cfg.favorites = []
        parent = params.get("parent") or favorites.FAVORITES_ROOT
        if favorites.is_favorite(cfg.favorites, params["media_id"], params["media_type"]):
            favorites.remove(cfg.favorites, params["media_id"], params["media_type"])
            self._persist_favorites()
            return self._build_confirmation(self.get_localized("Unpinned"), parent, paging)
        favorites.add(
            cfg.favorites,
            params["media_id"],
            params["media_type"],
            params.get("title") or params["media_id"],
        )
        self._persist_favorites()
        return self._build_confirmation(self.get_localized("Pinned"), parent, paging)

    def _handle_favorites_cleanup(self, paging: PaginationOptions) -> tuple[BrowseMediaItem, PaginationOptions]:
        """Remove all broken favorites."""
        cfg = self._device.device_config
        removed = favorites.remove_broken(cfg.favorites or [])
        if removed:
            self._persist_favorites()
        return self._build_confirmation(
            self.get_localized("Removed {0} broken favorites").replace("{0}", str(removed)),
            favorites.FAVORITES_ROOT,
            paging,
        )

    def _make_pin_item(self, media_id: str, media_type: str, title: str) -> BrowseMediaItem | None:
        """Build the pin/unpin entry. Returns None when the toggle URL would exceed 255 chars."""
        pinned = favorites.is_favorite(self._device.device_config.favorites, media_id, media_type)
        label_key = "📍 Unpin this folder" if pinned else "📍 Pin this folder"
        toggle_id = favorites.encode_toggle(media_id, media_type, title, parent=media_id)
        if len(toggle_id) > MAX_MEDIA_ID_LEN:
            _LOG.debug(
                "Skipping pin item, toggle media_id would exceed %d chars (%d) for %s",
                MAX_MEDIA_ID_LEN,
                len(toggle_id),
                media_id[:120],
            )
            return None
        return BrowseMediaItem(
            title=self.get_localized(label_key),
            media_id=toggle_id,
            media_class=MediaClass.DIRECTORY,
            media_type=MediaContentType.URL.value,
            can_browse=True,
            can_play=False,
            items=[],
        )

    def _maybe_inject_pin_item(self, item: BrowseMediaItem, media_id: str | None, media_type: str | None) -> None:
        """Insert the pin/unpin item at the top of ``item.items`` if applicable."""
        if not media_id or not item or not item.items:
            return
        if not favorites.can_pin(media_id, media_type):
            return
        title = item.title or media_id
        # Skip if already injected (defensive against double calls)
        if (
            item.items
            and isinstance(item.items[0], BrowseMediaItem)
            and (item.items[0].media_id or "").startswith(favorites.FAVORITES_TOGGLE_PREFIX)
        ):
            return
        # Insert just AFTER an existing back item if present, otherwise at top
        insert_at = 1 if item.items and item.items[0].title in ("..", self.get_localized("..")) else 0
        pin = self._make_pin_item(media_id, media_type or "", title)
        if pin is not None:
            item.items.insert(insert_at, pin)

    def get_localized(self, value: str) -> str:
        """Return localized value."""
        translation = TRANSLATIONS.get(value)
        if translation is None:
            return value
        translated = translation.get(self._device.app_language_code)
        if translated:
            return translated
        return value

    def get_root_item(
        self,
        media_class: MediaClass = MediaClass.DIRECTORY,
        media_type: MediaContentType = MediaContentType.URL,
    ) -> BrowseMediaItem:
        """Build root item."""
        return BrowseMediaItem(
            title=self.get_localized("Media Library"),
            media_id="library",
            media_class=media_class,
            media_type=media_type,
            can_browse=True,
            can_search=True,
            items=[],
        )

    def get_back_item(
        self,
        source: str,
        media_type: str = MediaContentType.URL.value,
        title="..",
        media_class: MediaClass | str = MediaClass.DIRECTORY,
    ) -> BrowseMediaItem:
        """Build source item."""
        if isinstance(media_class, MediaClass):
            media_class = media_class.value
        return BrowseMediaItem(
            title=self.get_localized(title),
            media_id=source,
            media_class=media_class,
            media_type=media_type,
            can_browse=True,
            can_search=True,
            items=[],
        )

    def get_item_from_file(
        self, file: dict[str, Any], media_type: str, extract_thumbnail=True
    ) -> BrowseMediaItem | None:
        """Build item from file. Returns None when media_id exceeds the ucapi 255-char cap."""
        media_id = file.get("file", "") or ""
        if len(media_id) > MAX_MEDIA_ID_LEN:
            _LOG.warning(
                "Skipping file entry, media_id exceeds %d chars: %s...",
                MAX_MEDIA_ID_LEN,
                media_id[:120],
            )
            return None
        label = strip_kodi_formatting(file.get("label", ""))
        if file.get("filetype", "directory") == "directory":
            return BrowseMediaItem(
                title=label,
                media_id=media_id,
                media_class=MediaClass.DIRECTORY,
                media_type=media_type,
                can_browse=True,
                can_play=False,
                can_search=True,
                items=[],
            )
        if extract_thumbnail:
            thumbnail: str = file.get("file")
            if thumbnail:
                thumbnail = self._device.client.get_thumbnail_from_file(thumbnail.rstrip("/"))
        else:
            thumbnail: str | None = None
        return BrowseMediaItem(
            title=label,
            media_id=media_id,
            media_class=MediaClass.VIDEO,
            media_type=media_type,
            can_browse=False,
            can_play=True,
            can_search=True,
            thumbnail=thumbnail,
            items=[],
        )

    def get_artwork_url(self, url: str) -> str | None:
        """Return artwork url."""
        return self._device.client.thumbnail_url(url)
        # if "@smb" in url:
        #     return self._device.client.thumbnail_url(url)
        # url = url.removeprefix("image://").removesuffix("/")
        # return urllib.parse.unquote(url)

    @staticmethod
    def get_duration(data: dict[str, Any]) -> int | None:
        """Extract duration from media."""
        duration: int | None = data.get("duration", data.get("runtime", None))
        if duration is None or duration == 0:
            duration = data.get("resume", {}).get("total", None)
        if duration == 0.0:
            duration = None
        return int(duration) if duration else None

    def get_item_from_movie(self, movie: dict[str, Any], parent_id: str) -> BrowseMediaItem:
        """Build item from movie."""
        art = get_artwork(movie.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        media_id = str(movie.get("movieid", 0))
        subtitles: list[str] = []
        if rating := movie.get("rating"):
            subtitles.append(f"{round(rating, 1)}")
        if year := movie.get("year"):
            subtitles.append(f"- {year}")
        position_set = False
        if resume := movie.get("resume"):
            position = resume.get("position", 0)
            duration = resume.get("total", 0)
            if position != 0 and duration != 0:
                position_set = True
                subtitles.append(time.strftime("%H:%M:%S", time.gmtime(position)))
        if not position_set and (playcount := movie.get("playcount", 0)):
            if playcount > 0:
                subtitles.append(self.get_localized("Watched"))

        subtitle = " ".join(subtitles)

        if parent_id:
            media_id = parent_id + "/" + media_id
        return BrowseMediaItem(
            title=movie.get("label", ""),
            subtitle=subtitle,
            media_id=media_id,
            media_class=MediaClass.MOVIE,
            media_type=MediaContentType.MOVIE,
            can_play=True,
            thumbnail=art,
            duration=MediaBrowser.get_duration(movie),
        )

    def get_item_from_episode(self, episode: dict[str, Any]) -> BrowseMediaItem | None:
        """Build item from episode. Returns None when media_id exceeds the ucapi 255-char cap."""
        art = get_artwork(episode.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        media_id = str(episode.get("file", ""))
        if len(media_id) > MAX_MEDIA_ID_LEN:
            _LOG.warning(
                "Skipping episode entry, media_id exceeds %d chars: %s...",
                MAX_MEDIA_ID_LEN,
                media_id[:120],
            )
            return None
        subtitles: list[str] = []
        # Not necessary, season and episode already in label
        # episode_season = None
        # if episode.get("season"):
        #     episode_season = "S" + str(episode.get("season"))
        # if episode.get("episode"):
        #     episode_season = "" if episode_season is None else episode_season
        #     episode_season += "E" + str(episode.get("episode"))
        # if episode_season:
        #     subtitles.append(episode_season)

        if rating := episode.get("rating"):
            subtitles.append(f"{round(rating, 1)}")

        position_set = False
        if resume := episode.get("resume"):
            position = resume.get("position", 0)
            duration = resume.get("total", 0)
            if position != 0 and duration != 0:
                position_set = True
                subtitles.append(time.strftime("%H:%M:%S", time.gmtime(position)))
        if not position_set and (playcount := episode.get("playcount", 0)):
            if playcount > 0:
                subtitles.append(self.get_localized("Watched"))

        subtitle = " ".join(subtitles)

        return BrowseMediaItem(
            title=episode.get("label", ""),
            subtitle=subtitle,
            media_id=media_id,
            media_class=MediaClass.EPISODE,
            media_type=MediaContentType.EPISODE,
            can_play=True,
            thumbnail=art,
            duration=MediaBrowser.get_duration(episode),
        )

    def get_item_from_tvshow(self, show: dict[str, Any], parent_id: str) -> BrowseMediaItem:
        """Build item from TV Show."""
        art = get_artwork(show.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        media_id = str(show.get("tvshowid", 0))
        if parent_id:
            media_id = parent_id + "/" + media_id
        return BrowseMediaItem(
            title=show.get("label", ""),
            media_id=media_id,
            media_class=MediaClass.TV_SHOW,
            media_type=MediaContentType.TV_SHOW,
            can_browse=True,
            can_search=True,
            thumbnail=art,
        )

    def get_item_from_season(self, season: dict[str, Any], parent_id: str) -> BrowseMediaItem:
        """Build item from TV Show season."""
        art = get_artwork(season.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        media_id = str(season.get("season", 0))
        if parent_id:
            media_id = parent_id + "/" + media_id
        return BrowseMediaItem(
            title=season.get("label", ""),
            media_id=media_id,
            media_class=MediaClass.SEASON,
            media_type=MediaContentType.SEASON,
            can_browse=True,
            can_search=True,
            thumbnail=art,
        )

    @staticmethod
    def get_parent_item_tvshow(media_id: str, media_type: str, media_class: str | None = None) -> BrowseMediaItem:
        """Build item from TV Show."""
        if media_class is None:
            media_class = media_type
        return BrowseMediaItem(
            title="..",
            media_id=media_id,
            media_class=media_class,
            media_type=media_type,
            can_browse=True,
            can_search=True,
        )

    def get_item_from_album(self, album: dict[str, Any], parent_id: str) -> BrowseMediaItem:
        """Build item from Album."""
        art = get_artwork(album.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        media_id = str(album.get("albumid", 0))
        if parent_id:
            media_id = parent_id + "/" + media_id
        artist = get_element(album.get("artist", None))
        duration: int | None = album.get("albumduration", None)
        return BrowseMediaItem(
            title=album.get("label", ""),
            media_id=media_id,
            media_class=MediaClass.ALBUM,
            media_type=MediaContentType.ALBUM,
            can_browse=True,
            can_search=True,
            thumbnail=art,
            album=album.get("label", None),
            artist=artist,
            duration=int(duration) if duration else None,
        )

    def get_item_from_artist(self, artist: dict[str, Any], parent_id: str) -> BrowseMediaItem:
        """Build item from Artist."""
        art = get_artwork(artist.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        artist_name = artist.get("label", "")
        media_id = str(artist.get("artistid", 0))
        if parent_id:
            media_id = f"{parent_id}/{media_id}?artist={quote(artist_name)}"
        return BrowseMediaItem(
            title=artist_name,
            media_id=media_id,
            media_class=MediaClass.ARTIST,
            media_type=MediaContentType.ARTIST,
            can_browse=True,
            can_search=True,
            thumbnail=art,
        )

    def get_item_from_song(self, song: dict[str, Any], albumid: str | None = None) -> BrowseMediaItem:
        """Build item from song."""
        # pylint: disable=W1405
        art = get_artwork(song.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        title = song.get("label", "")
        if song.get("track", None):
            title = f"{song.get('track', 0)}. {title}"
        if song.get("duration", None):
            duration = song.get("duration", 0)
            if duration >= 3600:
                title = f"{title} - {time.strftime('%H:%M:%S', time.gmtime(song.get('duration', 0)))}"
            else:
                title = f"{title} - {time.strftime('%M:%S', time.gmtime(song.get('duration', 0)))}"
        media_id = str(song.get("songid", 0))
        if albumid:
            media_id = f"{media_id};{albumid}"
        return BrowseMediaItem(
            title=title,
            media_id=media_id,
            media_class=MediaClass.MUSIC,
            media_type=MediaContentType.MUSIC,
            can_search=True,
            can_play=True,
            thumbnail=art,
            album=song.get("album", None),
            artist=get_element(song.get("artist", None)),
        )

    def get_item_from_genre(self, media_type: str, genre: dict[str, Any], parent_id: str) -> BrowseMediaItem:
        """Build item from TV Show."""
        art = get_artwork(genre.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        media_id = str(genre.get("genreid", 0))
        if parent_id:
            media_id = parent_id + "/" + media_id
        return BrowseMediaItem(
            title=genre.get("label", ""),
            media_id=media_id,
            media_class=MediaClass.GENRE,
            media_type=media_type + "/" + quote(genre.get("label", "")),
            can_browse=True,
            can_search=True,
            thumbnail=art,
        )

    def get_item_from_channel_group(self, group: dict[str, Any], parent_id: str) -> BrowseMediaItem:
        """Build item from a PVR channel group."""
        media_id = f"{parent_id}/{int(group.get('channelgroupid', 0))}"
        return BrowseMediaItem(
            title=group.get("label", ""),
            media_id=media_id,
            media_class=MediaClass.DIRECTORY,
            media_type="channelgroup",
            can_browse=True,
            can_search=False,
            items=[],
        )

    def get_item_from_channel(self, channel: dict[str, Any]) -> BrowseMediaItem:
        """Build item from a PVR channel (live TV / radio)."""
        thumbnail = channel.get("thumbnail") or channel.get("icon")
        if thumbnail:
            thumbnail = self.get_artwork_url(thumbnail)
        subtitles: list[str] = []
        broadcast_now = channel.get("broadcastnow") or {}
        broadcast_next = channel.get("broadcastnext") or {}
        if title_now := broadcast_now.get("title"):
            subtitles.append(f"{self.get_localized('Now')}: {title_now}")
        if title_next := broadcast_next.get("title"):
            subtitles.append(f"{self.get_localized('Next')}: {title_next}")
        subtitle: str | None = " | ".join(subtitles) if subtitles else None
        if subtitle is not None and len(subtitle) > 255:
            subtitle = subtitle[:252].rstrip() + "..."  # pylint: disable=E1136
        return BrowseMediaItem(
            title=channel.get("label", ""),
            subtitle=subtitle,
            media_id=str(channel.get("channelid", 0)),
            media_class=MediaClass.CHANNEL if hasattr(MediaClass, "CHANNEL") else MediaClass.VIDEO,
            media_type="channel",
            can_play=True,
            can_browse=False,
            thumbnail=thumbnail,
        )

    def get_item_from_addon(self, addon: dict[str, Any]) -> BrowseMediaItem:
        """Build item from a Kodi addon."""
        thumbnail = addon.get("thumbnail")
        if thumbnail:
            thumbnail = self.get_artwork_url(thumbnail)
        subtitle = strip_kodi_formatting(addon.get("description")) or None
        if subtitle:
            # ucapi BrowseMediaItem.subtitle is limited to 255 chars
            if len(subtitle) > 255:
                subtitle = subtitle[:252].rstrip() + "..."
        addon_id = str(addon.get("addonid", ""))
        return BrowseMediaItem(
            title=strip_kodi_formatting(addon.get("name")) or addon_id,
            subtitle=subtitle,
            # Addons are browsed via Kodi's virtual file system: plugin://<addonid>/
            media_id=f"plugin://{addon_id}/" if addon_id else "",
            media_class=MediaClass.APP if hasattr(MediaClass, "APP") else MediaClass.DIRECTORY,
            media_type="addondir",
            can_play=False,
            can_browse=True,
            thumbnail=thumbnail,
        )

    @staticmethod
    def get_sorting(sorting: str) -> dict[str, str]:
        """Build sorting method."""
        param = sorting.split(" ")
        result = {"method": param[0]}
        if len(param) > 1:
            result["order"] = param[1]
        return result

    def get_category(self, media_id: str) -> BrowseMediaItem | None:
        """Build category method."""
        found = [x.get_media_item() for x in self._library_items if x.media_id == media_id]
        if len(found) > 0:
            return found[0]
        return None

    async def add_now_playing_item(self, items: list[BrowseMediaItem], position: int):
        """Add now playing item."""
        current_playlist = await self._device.get_current_playlist()
        if current_playlist and current_playlist.position >= 0:
            playing = current_playlist.playlist["items"][current_playlist.position]
            art = get_artwork(playing.get("art", None))
            if art:
                art = self.get_artwork_url(art)
            duration = playing.get("duration", None)
            # ucapi rejects empty strings for album/artist ("must be at least 1
            # characters"); coerce "" to None to avoid aborting the whole root
            # listing when Kodi returns an empty tag.
            album = playing.get("album", None) or None
            artist = get_element(playing.get("artist", None)) or None
            items.insert(
                position,
                BrowseMediaItem(
                    title=f"{self.get_localized('Now playing')} " f"({playing.get('label', '')})",
                    media_class=MediaClass.PLAYLIST,
                    media_type=MediaClass.PLAYLIST,
                    media_id="kodi://playing",
                    thumbnail=art,
                    can_browse=True,
                    duration=int(duration) if duration else None,
                    album=album,
                    artist=artist,
                ),
            )

    def add_back_entry(self, media_id: str, paging: PaginationOptions | None) -> bool:
        """Check if a back entry should be added."""
        # Add back entry if back_support enabled or if the given media_id is a parent of custom category
        if (paging is None or paging.page == 1) and (
            self._back_support or self._device.device_config.browse_media_root.startswith(media_id)
        ):
            return True
        return False

    async def browse_media(
        self, media_id: str | None, media_type: str | None, paging: Paging | None
    ) -> tuple[BrowseMediaItem, PaginationOptions] | None:
        """Browse media."""
        # pylint: disable=R0914,R1702,R0911,R0915,W1405
        try:
            if paging is None:
                paging = PaginationOptions(page=1, limit=10, count=0)
            else:
                paging = PaginationOptions(page=paging.page, limit=paging.limit, count=0)

            # Change media_id if empty (root) and a custom category has been defined by user
            # add_now_playing = False
            if (media_id is None or media_id == "") and self._device.device_config.browse_media_root != "":
                media_id = self._device.device_config.browse_media_root
                # add_now_playing = True
                category = self.get_category(media_id)
                if category:
                    media_type = category.media_type

            # Return library root
            if media_id is None or media_id == "" or media_id == "kodi://":
                item = self.get_root_item()
                items = [x.get_media_item() for x in self._library_items if x.parent_id is None]
                items = await self._filter_optional_roots(items)

                # Add currently playing playlist if any
                await self.add_now_playing_item(items, 0)
                for sub_item in items:
                    sub_item.title = self.get_localized(sub_item.title)
                # Optionally inject favorites flat into the browse root
                if getattr(self._device.device_config, "favorites_in_root", False):
                    favs = favorites.list_favorites(self._device.device_config.favorites)
                    for fav in favs:
                        entry = self._favorite_item(fav)
                        if entry is not None:
                            items.insert(0, entry)
                paging.count = len(items)
                item.title = self.get_localized(item.title)
                item.items = items
                return item, paging

            # ---------- Favorites special routes ----------
            if media_id == favorites.FAVORITES_ROOT:
                return self._build_favorites_root(paging)
            if media_id == favorites.FAVORITES_MANAGE:
                return self._build_favorites_manage(paging)
            if media_id.startswith(favorites.FAVORITES_TOGGLE_PREFIX):
                return self._handle_favorites_toggle(media_id, paging)
            if media_id == favorites.FAVORITES_CLEANUP:
                return self._handle_favorites_cleanup(paging)
            # ----------------------------------------------

            # Find given media_id in the library items
            entry: KodiMediaEntry | None = None
            try:
                entry = next(iter([x for x in self._library_items if x.media_id == media_id]))
            except StopIteration:
                pass

            # If given media_id is a parent id, then the sub-items are predefined and we return them
            entries = [x for x in self._library_items if x.parent_id == media_id]
            if len(entries) > 0:
                for item in entries:
                    item.title = self.get_localized(item.title)
                sub_items = await self._filter_optional_roots([x.get_media_item() for x in entries])
                if entry is not None:
                    item = entry.get_media_item()
                    item.title = self.get_localized(item.title)
                    item.items = sub_items
                    paging.count = len(sub_items)
                else:
                    item = self.get_root_item()
                    item.items = sub_items
                    paging.count = len(sub_items)
                # Add back item if set or based on custom category
                if self.add_back_entry(item.media_id, paging):
                    parent_category = item.media_id[: item.media_id.rfind("/")]
                    if parent_category == "kodi:/":
                        parent_category = "kodi://"
                    parent = self.get_category(parent_category)
                    item.items.insert(
                        0,
                        self.get_back_item(parent_category, parent.media_type if parent else media_type),
                    )
                return item, paging

            # Given media_id is defined in the library items with a command to extract sub-items
            if entry is not None and entry.command is not None:
                arguments = entry.arguments.copy() if entry.arguments else {}
                item = entry.get_media_item()
                item.title = self.get_localized(item.title)
                limit = paging.limit
                end = paging.page * limit
                if self._back_support and paging.page == 1:
                    end -= 1
                arguments["limits"] = {
                    "start": (paging.page - 1) * limit,
                    "end": end,
                }
                # Add custom sorting field if configured
                if (
                    media_type in [MediaContentType.MOVIE.value, MediaContentType.VIDEO.value]
                    and self._device.device_config.browsing_video_sort
                    and arguments.get("sort") is None
                ):
                    arguments["sort"] = MediaBrowser.get_sorting(self._device.device_config.browsing_video_sort)
                elif (
                    media_type == MediaContentType.ALBUM.value
                    and self._device.device_config.browsing_album_sort
                    and arguments.get("sort") is None
                ):
                    arguments["sort"] = MediaBrowser.get_sorting(self._device.device_config.browsing_album_sort)
                elif (
                    entry.output == KodiObjectType.FILE
                    and self._device.device_config.browsing_files_sort
                    and arguments.get("sort") is None
                ):
                    arguments["sort"] = MediaBrowser.get_sorting(self._device.device_config.browsing_files_sort)

                _LOG.debug(
                    "[%s] Browsing command %s %s",
                    self._device.device_config.address,
                    entry.command,
                    arguments,
                )
                data = await self._device.client.call_method(entry.command, **arguments)
                paging.count = data.get("limits", {}).get("total", 0)
                if self.add_back_entry(item.media_id, None):
                    paging.count = paging.count + 1

                if entry.output == KodiObjectType.FILE:
                    # media_type = kodi://sources/<videos|music|pictures|files>
                    # Each files have following format : smb://...|nfs://...|multipath://...
                    if self.add_back_entry(item.media_id, paging):
                        item.items.append(self.get_back_item("kodi://sources"))
                    for file in data.get("files", data.get("sources", [])):
                        sub = self.get_item_from_file(file, media_type, False)
                        if sub is not None:
                            item.items.append(sub)
                elif entry.output == KodiObjectType.MOVIE:
                    if self.add_back_entry(item.media_id, paging):
                        item.items.append(self.get_back_item("kodi://videos", str(MediaContentType.MOVIE.value)))
                    if entry.media_id == "kodi://videos/music":
                        for movie in data.get("musicvideos", []):
                            item.items.append(self.get_item_from_movie(movie, media_id))
                    else:
                        for movie in data.get("movies", []):
                            item.items.append(self.get_item_from_movie(movie, media_id))
                elif entry.output == KodiObjectType.EPISODE:
                    if self.add_back_entry(item.media_id, paging):
                        item.items.append(self.get_back_item("kodi://tvshows", str(MediaContentType.TV_SHOW.value)))
                    for episode in data.get("episodes", []):
                        sub = self.get_item_from_episode(episode)
                        if sub is not None:
                            item.items.append(sub)
                elif entry.output == KodiObjectType.TV_SHOW:
                    if self.add_back_entry(item.media_id, paging):
                        item.items.append(self.get_back_item("kodi://tvshows", str(MediaContentType.TV_SHOW.value)))
                    for show in data.get("tvshows", []):
                        item.items.append(self.get_item_from_tvshow(show, media_id))
                elif entry.output == KodiObjectType.EPISODE:
                    if self.add_back_entry(item.media_id, paging):
                        item.items.append(self.get_back_item("kodi://tvshows", str(MediaContentType.TV_SHOW.value)))
                    for episode in data.get("episodes", []):
                        sub = self.get_item_from_episode(episode)
                        if sub is not None:
                            item.items.append(sub)
                elif entry.output == KodiObjectType.ALBUM:
                    if self.add_back_entry(item.media_id, paging):
                        item.items.append(self.get_back_item("kodi://music", str(MediaContentType.MUSIC.value)))
                    for album in data.get("albums", []):
                        item.items.append(self.get_item_from_album(album, media_id))
                elif entry.output == KodiObjectType.GENRE:
                    if self.add_back_entry(item.media_id, paging):
                        try:
                            if "/" in media_id:
                                parent_media_id = media_id[: media_id.rfind("/")]
                            else:
                                parent_media_id = media_id
                            item.items.append(self.get_back_item(parent_media_id, media_type))
                        # pylint: disable = W0718
                        except Exception:
                            pass
                    for genre in data.get("genres", []):
                        item.items.append(self.get_item_from_genre(media_type, genre, media_id))
                elif entry.output == KodiObjectType.ARTIST:
                    if self.add_back_entry(item.media_id, paging):
                        item.items.append(self.get_back_item("kodi://music", str(MediaContentType.MUSIC.value)))
                    for artist in data.get("artists", []):
                        item.items.append(self.get_item_from_artist(artist, media_id))
                elif entry.output == KodiObjectType.SONG:
                    if self.add_back_entry(item.media_id, paging):
                        item.items.append(self.get_back_item("kodi://music", str(MediaContentType.MUSIC.value)))
                    for song in data.get("songs", []):
                        item.items.append(self.get_item_from_song(song, media_id))
                elif entry.output == KodiObjectType.PLAYLIST:
                    if self.add_back_entry(item.media_id, paging):
                        item.items.append(self.get_back_item(entry.parent_id))
                    for media in data.get("files", []):
                        # Strip off extension file
                        media["label"] = os.path.splitext(media.get("label"))[0]
                        media["filetype"] = "file"
                        item.items.append(self.get_item_from_file(media, media_id, extract_thumbnail=False))
                elif entry.output == KodiObjectType.CHANNEL_GROUP:
                    if self.add_back_entry(item.media_id, paging):
                        item.items.append(self.get_back_item("kodi://pvr"))
                    for group in data.get("channelgroups", []):
                        item.items.append(self.get_item_from_channel_group(group, media_id))
                elif entry.output == KodiObjectType.CHANNEL:
                    if self.add_back_entry(item.media_id, paging):
                        item.items.append(self.get_back_item(entry.parent_id or "kodi://pvr"))
                    for channel in data.get("channels", []):
                        item.items.append(self.get_item_from_channel(channel))
                elif entry.output == KodiObjectType.ADDON:
                    if self.add_back_entry(item.media_id, paging):
                        item.items.append(self.get_back_item("kodi://addons"))
                    for addon in data.get("addons", []):
                        item.items.append(self.get_item_from_addon(addon))
                else:
                    _LOG.warning(
                        "[%s] Browsing unsupported output type %s for given media id %s and entry %s",
                        self._device.device_config.address,
                        entry.output,
                        media_id,
                        entry,
                    )
                    return None
                return item, paging
            # Else this is a subentry returned by a query command with browsing feature
            if entry is None and media_type:
                # Browsing inside a Kodi addon (plugin://...) - works like a Source
                if media_type == "addondir" or media_id.startswith("plugin://"):
                    item = self.get_root_item()
                    item.title = media_id
                    limit = paging.limit
                    end = paging.page * limit
                    arguments = {
                        "directory": media_id,
                        "media": "files",
                        "properties": ["title", "thumbnail", "art", "mimetype"],
                        "limits": {
                            "start": (paging.page - 1) * limit,
                            "end": end,
                        },
                    }
                    _LOG.debug(
                        "[%s] Browsing addon directory %s : %s",
                        self._device.device_config.address,
                        media_id,
                        arguments,
                    )
                    try:
                        data = await self._device.server.Files.GetDirectory(**arguments)
                    # pylint: disable=W0718
                    except Exception as ex:
                        _LOG.warning(
                            "[%s] Addon directory %s could not be listed: %s",
                            self._device.device_config.address,
                            media_id,
                            ex,
                        )
                        data = None
                        # If this id is a saved favorite, flag it as broken and
                        # always offer an unpin button so the user is not stuck.
                        cfg = self._device.device_config
                        if favorites.is_favorite(cfg.favorites, media_id, media_type or "addondir"):
                            if favorites.mark_broken(cfg.favorites, media_id, media_type or "addondir", True):
                                self._persist_favorites()
                            item.items.append(self._make_pin_item(media_id, media_type or "addondir", media_id))
                    if data:
                        for file in data.get("files", []) or []:
                            sub = self.get_item_from_file(file, "addondir", extract_thumbnail=False)
                            if sub is None:
                                continue
                            # Re-attach thumbnail from JSON-RPC response if present
                            thumb = file.get("thumbnail") or (file.get("art") or {}).get("thumb")
                            if thumb:
                                sub.thumbnail = self.get_artwork_url(thumb)
                            item.items.append(sub)
                        paging.count = data.get("limits", {}).get("total", len(item.items))
                        # If this directory is a saved favorite that was previously
                        # broken, clear the flag now that it works again.
                        cfg = self._device.device_config
                        if favorites.mark_broken(cfg.favorites, media_id, media_type or "addondir", False):
                            self._persist_favorites()
                    # Inject the pin/unpin shortcut at the top so the user can
                    # bookmark this exact location.
                    self._maybe_inject_pin_item(item, media_id, media_type or "addondir")
                    return item, paging
                if media_type.startswith("kodi://sources"):
                    back_buttons = 0
                    item = self.get_root_item()
                    if not media_id.startswith("multipath://"):
                        item.title = media_id
                    limit = paging.limit
                    end = paging.page * limit
                    media = KodiMediaTypes.VIDEOS.value
                    for key, kodi_type in SOURCE_MEDIA_TYPES_MAPPING.items():
                        if media_type.startswith(key):
                            media = kodi_type
                            break
                    # For source browsing, find upper folder from media_id except for multipath url
                    if self._back_support and paging.page == 1:
                        item.items.append(self.get_back_item(media_type, media_type, "Sources"))
                        back_buttons += 1
                        if not media_id.startswith("multipath://"):
                            try:
                                parent = media_id[: media_id.rstrip("/").rfind("/")]
                                item.items.append(self.get_back_item(parent, media_type))
                                back_buttons += 1
                            except IndexError:
                                pass

                        limit -= back_buttons
                    arguments: dict[str, Any] = {
                        "directory": media_id,
                        "properties": ["mimetype"],
                        "limits": {
                            "start": (paging.page - 1) * limit,
                            "end": end,
                        },
                    }
                    # Apply custom sorting for files browsing if defined
                    if self._device.device_config.browsing_files_sort:
                        arguments["sort"] = MediaBrowser.get_sorting(self._device.device_config.browsing_files_sort)
                    # Apply media filter on pictures only
                    if media == KodiMediaTypes.PICTURES.value:
                        arguments["media"] = media
                        item.media_type = KodiMediaTypes.PICTURES.value
                        item.media_class = KodiMediaTypes.PICTURES.value

                    _LOG.debug(
                        "[%s] Browsing source %s (%s) : %s",
                        self._device.device_config.address,
                        media_type,
                        media_id,
                        arguments,
                    )
                    data = await self._device.server.Files.GetDirectory(**arguments)
                    if data:
                        for file in data["files"]:
                            # Thumbnail extraction only works with pictures
                            extract_thumbnail = media == KodiMediaTypes.PICTURES.value
                            sub = self.get_item_from_file(file, media_type, extract_thumbnail)
                            if sub is not None:
                                item.items.append(sub)
                        paging.count = data.get("limits", {}).get("total", 0)
                        if self._back_support:
                            paging.count = paging.count + back_buttons
                    return item, paging
                # For the following media types, media_id is in format kodi://.../.../.../id
                if "/" in media_id and not media_id.endswith("/"):
                    real_media_id = media_id.rsplit("/", 1)[-1]
                    parent_id = media_id[: media_id.rstrip("/").rfind("/")]
                else:
                    real_media_id = media_id
                    parent_id = None

                if media_type == MediaContentType.TV_SHOW.value:
                    item = self.get_root_item(MediaClass.SEASON, MediaContentType.SEASON)
                    limit = paging.limit
                    end = paging.page * limit
                    if self._back_support and paging.page == 1:
                        item.items.append(
                            self.get_back_item(
                                parent_id if parent_id else "kodi://tvshows",
                                parent_id if parent_id else "kodi://tvshows",
                            )
                        )
                        end -= 1
                    arguments = {
                        "properties": ["art", "season", "showtitle"],
                        "tvshowid": int(real_media_id),
                        "limits": {
                            "start": (paging.page - 1) * limit,
                            "end": end,
                        },
                    }
                    _LOG.debug(
                        "[%s] Browsing seasons %s (%s) : %s",
                        self._device.device_config.address,
                        media_type,
                        media_id,
                        arguments,
                    )
                    seasons = await self._device.server.VideoLibrary.GetSeasons(**arguments)
                    if len(seasons["seasons"]) > 0:
                        item.title = seasons["seasons"][0].get("showtitle", "")
                    paging.count = seasons.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging.count = paging.count + 1
                    for season in seasons["seasons"]:
                        item.items.append(self.get_item_from_season(season, media_id))
                elif media_type == MediaContentType.SEASON.value:
                    show_id = parent_id.rsplit("/", 1)[-1]
                    season = real_media_id
                    item = self.get_root_item(MediaClass.EPISODE, MediaContentType.EPISODE)
                    limit = paging.limit
                    end = paging.page * limit
                    if self._back_support and paging.page == 1:
                        # "kodi://tvshows/genres/5/32/1"
                        MediaBrowser.get_parent_item_tvshow(str(parent_id), str(MediaContentType.TV_SHOW.value))
                        item.items.append(
                            MediaBrowser.get_parent_item_tvshow(str(parent_id), str(MediaContentType.TV_SHOW.value))
                        )
                        end -= 1
                    arguments = {
                        "properties": EPISODE_PROPERTIES,
                        "tvshowid": int(show_id),
                        "season": int(season),
                        "limits": {
                            "start": (paging.page - 1) * limit,
                            "end": end,
                        },
                    }
                    _LOG.debug(
                        "[%s] Browsing episodes %s (%s) : %s",
                        self._device.device_config.address,
                        media_type,
                        media_id,
                        arguments,
                    )
                    episodes = await self._device.server.VideoLibrary.GetEpisodes(**arguments)
                    if len(episodes["episodes"]) > 0:
                        try:
                            item.title = (
                                episodes["episodes"][0]["showtitle"] + " - " + str(episodes["episodes"][0]["season"])
                            )
                        except Exception:  # pylint: disable = W0718
                            pass
                    paging.count = episodes.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging.count = paging.count + 1
                    if len(episodes["episodes"]) > 0:
                        show_title = episodes["episodes"][0].get("showtitle", "")
                        item.title = f"{show_title} - S{season}"
                    for episode in episodes["episodes"]:
                        sub = self.get_item_from_episode(episode)
                        if sub is not None:
                            item.items.append(sub)

                elif media_type == MediaContentType.ALBUM.value:
                    item = self.get_root_item(MediaClass.ALBUM, MediaContentType.MUSIC)
                    limit = paging.limit
                    end = paging.page * limit
                    if self._back_support and paging.page == 1:
                        if parent_id.startswith("kodi://music/artists"):
                            parent_media_class = MediaClass.ARTIST
                            parent_media_type = MediaContentType.ARTIST
                        elif parent_id.startswith("kodi://music/genres"):
                            parent_id = "kodi://music/genres"
                            parent_media_class = MediaClass.GENRE
                            parent_media_type = "kodi://music/genres"
                        else:
                            parent_media_class = MediaClass.MUSIC
                            parent_media_type = MediaContentType.ALBUM
                        item.items.append(
                            self.get_back_item(
                                parent_id if parent_id else "kodi://music",
                                str(parent_media_type.value),
                                "..",
                                parent_media_class,
                            )
                        )
                        end -= 1
                    arguments = {
                        "properties": ["art", "duration", "track", "album", "artist"],
                        "filter": {"albumid": int(real_media_id)},
                        "limits": {
                            "start": (paging.page - 1) * limit,
                            "end": end,
                        },
                    }
                    _LOG.debug(
                        "[%s] Browsing songs %s (%s) : %s",
                        self._device.device_config.address,
                        media_type,
                        media_id,
                        arguments,
                    )
                    songs = await self._device.server.AudioLibrary.GetSongs(**arguments)
                    paging.count = songs.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging.count = paging.count + 1
                    for song in songs["songs"]:
                        item.items.append(self.get_item_from_song(song, real_media_id))
                    if len(item.items) > 0 and (album := item.items[0].album):
                        item.title = album
                        item.album = album

                elif media_type == MediaContentType.ARTIST.value:
                    item = self.get_root_item(MediaClass.MUSIC, MediaContentType.ALBUM)
                    limit = paging.limit
                    end = paging.page * limit
                    if self._back_support and paging.page == 1:
                        item.items.append(
                            self.get_back_item(
                                parent_id if parent_id else "kodi://music",
                                str(MediaContentType.MUSIC.value),
                            )
                        )
                        end -= 1
                    # real_media_id = <artistid>?=<artist name quoted>
                    artist_id_name = real_media_id.split("?artist=", 1)
                    artist_id = int(artist_id_name[0])
                    artist_name = None if len(artist_id_name) == 1 else unquote(artist_id_name[1])
                    if artist_name:
                        item.title = artist_name
                    arguments = {
                        "properties": ["art", "artist", "albumduration"],
                        "filter": {"artistid": artist_id},
                        "limits": {
                            "start": (paging.page - 1) * limit,
                            "end": end,
                        },
                    }
                    _LOG.debug(
                        "[%s] Browsing artist albums (%s) : %s",
                        self._device.device_config.address,
                        media_id,
                        arguments,
                    )
                    albums = await self._device.server.AudioLibrary.GetAlbums(**arguments)
                    paging.count = albums.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging.count = paging.count + 1
                    for album in albums["albums"]:
                        item.items.append(self.get_item_from_album(album, media_id))
                elif media_type.startswith("kodi://videos/genres"):
                    genre = unquote(media_type.replace("kodi://videos/genres/", ""))
                    item = self.get_root_item(MediaClass.MOVIE, MediaContentType.MOVIE)
                    limit = paging.limit
                    end = paging.page * limit
                    if self._back_support and paging.page == 1:
                        item.items.append(
                            self.get_back_item(
                                parent_id if parent_id else "kodi://videos/genres",
                                parent_id if parent_id else "kodi://videos/genres",
                            )
                        )
                        end -= 1
                    arguments = {
                        "properties": MOVIE_PROPERTIES,
                        "filter": {"genreid": int(real_media_id)},
                        "limits": {
                            "start": (paging.page - 1) * limit,
                            "end": end,
                        },
                    }
                    if self._device.device_config.browsing_video_sort:
                        arguments["sort"] = MediaBrowser.get_sorting(self._device.device_config.browsing_video_sort)

                    _LOG.debug(
                        "[%s] Browsing videos genre %s (%s) : %s",
                        self._device.device_config.address,
                        media_type,
                        media_id,
                        arguments,
                    )
                    medias = await self._device.server.VideoLibrary.GetMovies(**arguments)
                    item.title = genre
                    paging.count = medias.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging.count = paging.count + 1
                    for media in medias["movies"]:
                        item.items.append(self.get_item_from_movie(media, media_id))
                elif media_type.startswith("kodi://tvshows/genres/"):
                    genre = unquote(media_type.replace("kodi://tvshows/genres/", ""))
                    item = self.get_root_item(MediaClass.TV_SHOW, MediaContentType.TV_SHOW)
                    limit = paging.limit
                    end = paging.page * limit
                    if self._back_support and paging.page == 1:
                        item.items.append(
                            self.get_back_item(
                                parent_id if parent_id else "kodi://tvshows/genres",
                                parent_id if parent_id else "kodi://tvshows/genres",
                            )
                        )
                        end -= 1
                    arguments = {
                        "properties": ["art", "genre"],
                        "filter": {"genreid": int(real_media_id)},
                        "limits": {
                            "start": (paging.page - 1) * limit,
                            "end": end,
                        },
                    }
                    _LOG.debug(
                        "[%s] Browsing TV shows genre %s (%s) : %s",
                        self._device.device_config.address,
                        media_type,
                        media_id,
                        arguments,
                    )
                    medias = await self._device.server.VideoLibrary.GetTVShows(**arguments)
                    item.title = genre
                    # if len(medias["tvshows"]) > 0:
                    #     try:
                    #         item.title = medias["tvshows"][0]["genre"]
                    #     except Exception:  # pylint: disable = W0718
                    #         pass
                    paging.count = medias.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging.count = paging.count + 1
                    for media in medias["tvshows"]:
                        item.items.append(self.get_item_from_tvshow(media, media_id))
                elif media_type.startswith("kodi://music/genres"):
                    item = self.get_root_item(MediaClass.ALBUM, MediaContentType.ALBUM)
                    limit = paging.limit
                    end = paging.page * limit
                    if self._back_support and paging.page == 1:
                        item.items.append(
                            self.get_back_item(
                                parent_id if parent_id else "kodi://music",
                                str(MediaContentType.MUSIC.value),
                            )
                        )
                        end -= 1
                    arguments = {
                        "properties": ["art", "genre", "albumduration", "artist"],
                        "filter": {"genreid": int(real_media_id)},
                        "limits": {
                            "start": (paging.page - 1) * limit,
                            "end": end,
                        },
                    }
                    if self._device.device_config.browsing_album_sort:
                        arguments["sort"] = MediaBrowser.get_sorting(self._device.device_config.browsing_album_sort)
                    _LOG.debug(
                        "[%s] Browsing music genre %s (%s) : %s",
                        self._device.device_config.address,
                        media_type,
                        media_id,
                        arguments,
                    )

                    medias = await self._device.server.AudioLibrary.GetAlbums(**arguments)
                    if len(medias["albums"]) > 0:
                        try:
                            item.title = medias["albums"][0]["genre"][0]
                        except Exception:  # pylint: disable = W0718
                            pass
                    paging.count = medias.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging.count = paging.count + 1
                    for album in medias.get("albums", []):
                        item.items.append(self.get_item_from_album(album, media_id))
                elif media_type == "channelgroup":
                    # Dynamic channel listing for a PVR group: media_id = kodi://pvr/<tv|radio>/<groupid>
                    item = self.get_root_item(MediaClass.DIRECTORY, "channelgroup")
                    limit = paging.limit
                    end = paging.page * limit
                    parent_back = parent_id or "kodi://pvr"
                    if self._back_support and paging.page == 1:
                        item.items.append(self.get_back_item(parent_back, parent_back))
                        end -= 1
                    arguments = {
                        "channelgroupid": int(real_media_id),
                        "properties": [
                            "thumbnail",
                            "channeltype",
                            "broadcastnow",
                            "broadcastnext",
                            "channel",
                            "lastplayed",
                            "hidden",
                            "locked",
                        ],
                        "limits": {
                            "start": (paging.page - 1) * limit,
                            "end": end,
                        },
                    }
                    _LOG.debug(
                        "[%s] Browsing PVR channels (%s) : %s",
                        self._device.device_config.address,
                        media_id,
                        arguments,
                    )
                    channels = await self._device.server.PVR.GetChannels(**arguments)
                    paging.count = channels.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging.count = paging.count + 1
                    for channel in channels.get("channels", []):
                        item.items.append(self.get_item_from_channel(channel))
                    # Allow pinning of the whole channel group
                    self._maybe_inject_pin_item(item, media_id, "channelgroup")
                elif media_type == MediaContentType.PLAYLIST.value:
                    item = self.get_root_item(MediaClass.PLAYLIST, MediaContentType.PLAYLIST)
                    limit = paging.limit
                    end = paging.page * limit

                    if self._back_support and paging.page == 1:
                        item.items.append(self.get_back_item("kodi://"))
                        end -= 1
                    current_playlist = await self._device.get_current_playlist()
                    if current_playlist:
                        position = 0
                        tag_current = len(current_playlist.playlist["items"]) > 1
                        for playlist_item in current_playlist.playlist["items"]:
                            media_type = (
                                MediaClass.MOVIE if playlist_item.get("type", "movie") == "movie" else MediaClass.MUSIC
                            )
                            duration = playlist_item.get("duration", None)
                            item.items.append(
                                BrowseMediaItem(
                                    title=(
                                        playlist_item.get("label", "")
                                        if position != current_playlist.position or not tag_current
                                        else f">> {playlist_item.get('label', '')} <<"
                                    ),
                                    media_class=MediaClass(media_type.value),
                                    media_type=MediaContentType.PLAYLIST,
                                    media_id=f"kodi://playlist/{current_playlist.playlist_id}/{position}",
                                    can_play=True,
                                    can_search=True,
                                    subtitle=(str(playlist_item.get("year")) if playlist_item.get("year") else None),
                                    album=playlist_item.get("album", None),
                                    artist=get_element(playlist_item.get("artist", None)),
                                    duration=int(duration) if duration else None,
                                )
                            )
                            position += 1
                        paging.count = current_playlist.playlist.get("limits", {}).get("total", 0)
                        if self._back_support:
                            paging.count = paging.count + 1
                else:
                    _LOG.warning(
                        "[%s] Browsing unknown media type %s for given media id %s",
                        self._device.device_config.address,
                        media_type,
                        media_id,
                    )
                    return None
                return item, paging
        # pylint: disable = W0718
        except Exception as ex:
            _LOG.exception(
                "[%s] Error while browsing media %s,%s : %s",
                self._device.device_config.address,
                media_id,
                media_type,
                ex,
            )
        if paging is None:
            paging = PaginationOptions(page=1, limit=10, count=0)
        else:
            paging = PaginationOptions(page=paging.page, limit=paging.limit, count=paging.count)

        # Return library root
        items = [x.get_media_item() for x in self._library_items if x.parent_id is None]
        for item in items:
            item.title = self.get_localized(item.title)
        paging.count = len(items)
        item = self.get_root_item()
        item.title = self.get_localized(item.title)
        item.items = items
        return item, paging

    async def enqueue_item(self, item: dict[str, Any], is_video=True):
        """Enqueue item to playlist."""
        playlist_id = 1 if is_video else 0
        current_playlist = await self._device.get_current_playlist()
        play = False
        # Kodi JSON RPC doesn't support adding to next playing item, only enqueue at the end
        if current_playlist.playlist_id != playlist_id or len(current_playlist.playlist.get("items", [])) == 0:
            play = True
        _LOG.debug(
            "[%s] Enqueue playlist %s item %s",
            self._device.device_config.address,
            playlist_id,
            item,
        )
        await self._device.server.Playlist.Add(**{"playlistid": playlist_id, "item": item})
        if play:
            _LOG.debug(
                "[%s] Playing playlist %s",
                self._device.device_config.address,
                playlist_id,
            )
            await self._device.server.Player.Open(**{"item": {"playlistid": playlist_id, "position": 0}})

    async def play_media(self, params: dict[str, Any]) -> StatusCodes:
        """Play given media id."""
        # pylint: disable=W1405,R0914,R0915,R0911
        media_id: str | None = params.get("media_id")
        media_type: str | None = params.get("media_type")
        action = params.get("action", "PLAY_NOW")
        enqueue = action != "PLAY_NOW"
        is_video = True
        item: dict[str, Any] = {}
        if media_id is None or media_type is None:
            return StatusCodes.BAD_REQUEST
        if media_type == "channel":
            if media_id.startswith("kodi://"):
                media_id = media_id.rstrip("/").rsplit("/", 1)[-1]
            _LOG.debug("[%s] Playing PVR channel id %s", self._device.device_config.address, media_id)
            await self._device.server.Player.Open(**{"item": {"channelid": int(media_id)}})
            return StatusCodes.OK
        if media_type == "addon":
            addon_id = media_id
            if addon_id.startswith("kodi://"):
                addon_id = addon_id.rstrip("/").rsplit("/", 1)[-1]
            _LOG.debug("[%s] Executing Kodi addon %s", self._device.device_config.address, addon_id)
            await self._device.server.Addons.ExecuteAddon(**{"addonid": addon_id, "wait": False})
            return StatusCodes.OK
        # Playable item from inside an addon (plugin://...)
        if media_id.startswith("plugin://"):
            _LOG.debug("[%s] Playing addon item %s", self._device.device_config.address, media_id)
            await self._device.server.Player.Open(**{"item": {"file": media_id}})
            return StatusCodes.OK
        if media_type == MediaContentType.MOVIE.value:
            if media_id.startswith("kodi://"):
                media_id = media_id.rstrip("/").rsplit("/", 1)[-1]
            _LOG.debug("[%s] Playing movie id %s", self._device.device_config.address, media_id)
            item = {"movieid": int(media_id)}
        if media_type == MediaContentType.EPISODE.value:
            if media_id.startswith("kodi://"):
                media_id = media_id.rstrip("/").rsplit("/", 1)[-1]
            _LOG.debug("[%s] Playing media id %s", self._device.device_config.address, media_id)
            item = {"file": media_id}
        elif media_type == MediaContentType.MUSIC.value:
            media_data = media_id.split(";")
            is_video = False
            if len(media_data) == 1:
                arguments = {"item": {"songid": int(media_data[0])}}
                _LOG.debug(
                    "[%s] Playing music %s",
                    self._device.device_config.address,
                    arguments,
                )
                item = {"songid": int(media_data[0])}
            else:
                song_id = int(media_data[0])
                album_id = int(media_data[1])
                await self._device.server.Playlist.Clear(**{"playlistid": 0})
                await self._device.server.Playlist.Add(**{"playlistid": 0, "item": {"albumid": album_id}})
                playlist = await self._device.client.call_method(
                    "AudioLibrary.GetSongs",
                    **{
                        "filter": {"albumid": album_id},
                        "properties": ["track"],
                        "sort": {"method": "track"},
                    },
                )
                position = 0
                for song in playlist.get("songs", []):
                    if song.get("songid", -1) == song_id:
                        break
                    position += 1
                _LOG.debug(
                    "[%s] Playing album %s",
                    self._device.device_config.address,
                    {"item": {"playlistid": 0, "position": position}},
                )
                await self._device.server.Player.Open(**{"item": {"playlistid": 0, "position": position}})
                return StatusCodes.OK
        elif media_type == MediaContentType.ALBUM.value:
            _LOG.debug("[%s] Playing album %s", self._device.device_config.address, media_id)
            is_video = False
            item = {"albumid": int(media_id)}
        elif media_type == MediaContentType.URL.value or media_type.startswith("kodi://sources"):
            _LOG.debug("[%s] Playing file %s", self._device.device_config.address, media_id)
            await self._device.server.Player.Open(**{"item": {"file": media_id}})
            return StatusCodes.OK
        elif media_type in ["kodi://videos/playlists", "kodi://music/playlists"]:
            _LOG.debug("[%s] Playing playlist %s", self._device.device_config.address, media_id)
            await self._device.server.Player.Open(**{"item": {"file": media_id}})
            return StatusCodes.OK
        elif media_id.startswith("kodi://playlist/"):
            media_data = media_id.split("/")
            playlist_id = int(media_data[-2])
            position = int(media_data[-1])
            _LOG.debug(
                "[%s] Playing playlist %s position %s",
                self._device.device_config.address,
                playlist_id,
                position,
            )
            await self._device.server.Player.Open(**{"item": {"playlistid": playlist_id, "position": position}})
            return StatusCodes.OK
        if enqueue:
            await self.enqueue_item(item, is_video=is_video)
        else:
            await self._device.server.Player.Open(**{"item": item})
        return StatusCodes.OK

    async def search_movies(
        self,
        query,
        media_id: str | None,
        media_type: str | None,
        paging: PaginationOptions,
        max_results: int,
    ) -> tuple[list[BrowseMediaItem], PaginationOptions]:
        """Search for movies."""
        results: list[BrowseMediaItem] = []
        limit = paging.limit
        if max_results > 0:
            end = max_results * limit
        else:
            end = paging.page * limit
        arguments: dict[str, Any] = {
            "properties": MOVIE_PROPERTIES,
            "limits": {
                "start": (paging.page - 1) * limit,
                "end": end,
            },
        }
        if len(query) > 0:
            arguments["filter"] = {
                "field": "title",
                "operator": "contains",
                "value": query,
            }
        _LOG.debug(
            "[%s] Searching video %s (media id %s, type %s) : %s",
            self._device.device_config.address,
            query,
            media_type,
            media_id,
            arguments,
        )
        medias = await self._device.server.VideoLibrary.GetMovies(**arguments)
        _LOG.debug(
            "[%s] Searching video results %s",
            self._device.device_config.address,
            medias,
        )
        new_paging = PaginationOptions(page=paging.page, limit=paging.limit, count=paging.count)
        new_paging.count += medias.get("limits", {}).get("total", 0)
        for media in medias["movies"]:
            results.append(self.get_item_from_movie(media, "kodi://videos/all"))
        return results, new_paging

    async def search_tv_shows(
        self,
        query,
        media_id: str | None,
        media_type: str | None,
        paging: PaginationOptions,
        max_results: int,
    ) -> tuple[list[BrowseMediaItem], PaginationOptions]:
        """Search for TV Shows."""
        results: list[BrowseMediaItem] = []
        limit = paging.limit
        if max_results > 0:
            end = max_results * limit
        else:
            end = paging.page * limit
        arguments: dict[str, Any] = {
            "properties": ["art"],
            "limits": {
                "start": (paging.page - 1) * limit,
                "end": end,
            },
        }
        if len(query) > 0:
            arguments["filter"] = {
                "field": "title",
                "operator": "contains",
                "value": query,
            }
        _LOG.debug(
            "[%s] Searching TV Shows %s (%s) : %s",
            self._device.device_config.address,
            media_type,
            media_id,
            arguments,
        )
        medias = await self._device.server.VideoLibrary.GetTVShows(**arguments)
        new_paging = PaginationOptions(page=paging.page, limit=paging.limit, count=paging.count)
        new_paging.count += medias.get("limits", {}).get("total", 0)
        for media in medias["tvshows"]:
            results.append(self.get_item_from_tvshow(media, "kodi://tvshows"))
        return results, new_paging

    async def search_albums(
        self,
        query,
        media_id: str | None,
        media_type: str | None,
        paging: PaginationOptions,
        max_results: int,
    ) -> tuple[list[BrowseMediaItem], PaginationOptions]:
        """Search for Albums."""
        results: list[BrowseMediaItem] = []
        limit = paging.limit
        if max_results > 0:
            end = max_results * limit
        else:
            end = paging.page * limit
        arguments: dict[str, Any] = {
            "properties": ["art", "artist", "albumduration"],
            "limits": {
                "start": (paging.page - 1) * limit,
                "end": end,
            },
        }
        if len(query) > 0:
            arguments["filter"] = {
                "or": [
                    {"field": "album", "operator": "contains", "value": query},
                    {"field": "artist", "operator": "contains", "value": query},
                ]
            }
        _LOG.debug(
            "[%s] Searching albums %s (%s) : %s",
            self._device.device_config.address,
            media_type,
            media_id,
            arguments,
        )
        medias = await self._device.server.AudioLibrary.GetAlbums(**arguments)
        new_paging = PaginationOptions(page=paging.page, limit=paging.limit, count=paging.count)
        new_paging.count += medias.get("limits", {}).get("total", 0)
        for media in medias["albums"]:
            results.append(self.get_item_from_album(media, "kodi://music/albums"))
        return results, new_paging

    async def search_artists(
        self,
        query,
        media_id: str | None,
        media_type: str | None,
        paging: PaginationOptions,
        max_results: int,
    ) -> tuple[list[BrowseMediaItem], PaginationOptions]:
        """Search for Artists."""
        results: list[BrowseMediaItem] = []
        limit = paging.limit
        if max_results > 0:
            end = max_results * limit
        else:
            end = paging.page * limit
        arguments: dict[str, Any] = {
            "properties": ["thumbnail"],
            "limits": {
                "start": (paging.page - 1) * limit,
                "end": end,
            },
        }
        if len(query) > 0:
            arguments["filter"] = {
                "field": "artist",
                "operator": "contains",
                "value": query,
            }
        _LOG.debug(
            "[%s] Searching artists %s (%s) : %s",
            self._device.device_config.address,
            media_type,
            media_id,
            arguments,
        )
        medias = await self._device.server.AudioLibrary.GetArtists(**arguments)
        new_paging = PaginationOptions(page=paging.page, limit=paging.limit, count=paging.count)
        new_paging.count += medias.get("limits", {}).get("total", 0)
        for media in medias["artists"]:
            results.append(self.get_item_from_artist(media, "kodi://music/artists"))
        return results, new_paging

    async def search_songs(
        self,
        query,
        media_id: str | None,
        media_type: str | None,
        paging: PaginationOptions,
        media_search_filter: SearchMediaFilter | None,
        max_results: int,
    ) -> tuple[list[BrowseMediaItem], PaginationOptions]:
        """Search for Songs."""
        results: list[BrowseMediaItem] = []
        limit = paging.limit
        if max_results > 0:
            end = max_results * limit
        else:
            end = paging.page * limit
        arguments: dict[str, Any] = {
            "properties": ["art", "duration", "track", "albumid"],
            "limits": {
                "start": (paging.page - 1) * limit,
                "end": end,
            },
        }
        if len(query) > 0:
            arguments["filter"] = {
                "or": [
                    # {"field": "title", "operator": "contains", "value": query},
                    {"field": "album", "operator": "contains", "value": query},
                    {"field": "artist", "operator": "contains", "value": query},
                ]
            }
        if media_search_filter:
            if media_search_filter.album:
                arguments["filter"] = {
                    "and": [
                        {
                            "field": "album",
                            "operator": "contains",
                            "value": media_search_filter.album,
                        },
                        {
                            "or": [
                                {
                                    "field": "title",
                                    "operator": "contains",
                                    "value": query,
                                },
                                {
                                    "field": "artist",
                                    "operator": "contains",
                                    "value": query,
                                },
                            ]
                        },
                    ]
                }
            elif media_search_filter.artist:
                arguments["filter"] = {
                    "and": [
                        {
                            "field": "artist",
                            "operator": "contains",
                            "value": media_search_filter.artist,
                        },
                        {
                            "or": [
                                {
                                    "field": "title",
                                    "operator": "contains",
                                    "value": query,
                                },
                                {
                                    "field": "album",
                                    "operator": "contains",
                                    "value": query,
                                },
                            ]
                        },
                    ]
                }

        _LOG.debug(
            "[%s] Searching songs %s (%s) : %s",
            self._device.device_config.address,
            media_type,
            media_id,
            arguments,
        )
        medias = await self._device.server.AudioLibrary.GetSongs(**arguments)
        new_paging = PaginationOptions(page=paging.page, limit=paging.limit, count=paging.count)
        new_paging.count += medias.get("limits", {}).get("total", 0)
        for media in medias["songs"]:
            results.append(self.get_item_from_song(media, str(media.get("albumid", 0))))
        return results, new_paging

    # pylint: disable=R0917,R0914
    async def search_media(
        self,
        query: str,
        media_id: str | None,
        media_type: str | None,
        media_search_filter: SearchMediaFilter | None,  # pylint: disable=W0613
        paging: Paging | None,
    ) -> tuple[list[BrowseMediaItem], PaginationOptions] | None:
        """Search media from given query and optional parameters."""
        # pylint: disable=R0915
        try:
            if paging is None:
                paging = PaginationOptions(page=1, limit=10, count=0)
            else:
                paging = PaginationOptions(page=paging.page, limit=paging.limit, count=0)
            max_results = paging.limit
            paging.count = 0
            media_classes: list[str] = []
            if (search_filter := media_search_filter) and (search_media_classes := search_filter.media_classes):
                for x in search_media_classes:
                    media_classes.append(x.value if isinstance(x, MediaClass) else x)

            results: list[BrowseMediaItem] = []
            search_filters = media_classes
            if len(search_filters) == 0:
                if media_type is None:
                    search_filters = [
                        str(MediaContentType.MOVIE.value),
                        str(MediaContentType.TV_SHOW.value),
                        str(MediaContentType.ALBUM.value),
                        str(MediaContentType.ARTIST.value),
                        str(MediaContentType.TRACK.value),
                    ]
                else:
                    search_filters = [media_type]
            _LOG.debug("[%s] Search media %s (%s)", self._device.device_config.address, query, search_filters)

            if MediaContentType.MOVIE.value in search_filters:
                movies, local_paging = await self.search_movies(query, media_id, media_type, paging, max_results)
                paging.count += local_paging.count
                max_results -= len(movies)
                results.extend(movies)
            if max_results > 0 and MediaContentType.TV_SHOW.value in search_filters:
                # if media_type is None and len(results) < paging.limit and paging.page == 1:
                #     end = limit - len(results)
                tv_shows, local_paging = await self.search_tv_shows(query, media_id, media_type, paging, max_results)
                paging.count += local_paging.count
                max_results -= len(tv_shows)
                results.extend(tv_shows)
            if max_results > 0 and MediaContentType.ALBUM.value in search_filters:
                albums, local_paging = await self.search_albums(query, media_id, media_type, paging, max_results)
                paging.count += local_paging.count
                max_results -= len(albums)
                results.extend(albums)
            if max_results > 0 and MediaContentType.ARTIST.value in search_filters:
                artists, local_paging = await self.search_artists(query, media_id, media_type, paging, max_results)
                paging.count += local_paging.count
                max_results -= len(artists)
                results.extend(artists)
            if max_results > 0 and (
                MediaContentType.TRACK.value in search_filters or MediaContentType.MUSIC.value in search_filters
            ):
                songs, local_paging = await self.search_songs(
                    query,
                    media_id,
                    media_type,
                    paging,
                    media_search_filter,
                    max_results,
                )
                paging.count += local_paging.count
                max_results -= len(songs)
                results.extend(songs)

            _LOG.debug(
                "[%s] Searching results %s %s",
                self._device.device_config.address,
                results,
                paging,
            )
            return results, paging
        # pylint: disable = W0718
        except Exception as ex:
            _LOG.exception(
                "[%s] Error while searching media %s, %s, %s : %s",
                self._device.device_config.address,
                query,
                media_id,
                media_type,
                ex,
            )
        return [], paging


@dataclass
class KodiMediaEntry:
    """Media entry for browsing media."""

    title: str
    media_type: MediaContentType | str
    child_media_type: MediaContentType
    media_id: str
    output: KodiObjectType
    media_class: MediaClass | None = field(default=None)
    parent_id: str | None = field(default=None)
    command: str | None = field(default=None)
    arguments: dict[str, Any] = field(default=None)

    def __post_init__(self):
        """Apply default values on missing fields."""
        for attribute in fields(self):
            # If there is a default and the value of the field is none we can assign a value
            if (
                not isinstance(attribute.default, dataclasses.MISSING.__class__)
                and getattr(self, attribute.name) is None
            ):
                setattr(self, attribute.name, attribute.default)

    @property
    def media_type_str(self) -> str:
        """Return media content type in string format."""
        return self.media_type.value if isinstance(self.media_type, MediaContentType) else self.media_type

    @property
    def media_class_str(self) -> str | None:
        """Return media class in string format."""
        return self.media_class.value if self.media_class else None

    def get_media_item(self) -> BrowseMediaItem:
        """Build media item."""
        return BrowseMediaItem(
            title=self.title,
            media_id=self.media_id,
            media_type=self.media_type_str,
            media_class=(self.media_type_str if self.media_class is None else self.media_class_str),
            can_browse=True,
            can_search=True,
            items=[],
        )

    def get_parent_item(self) -> BrowseMediaItem | None:
        """Build parent item."""
        try:
            return BrowseMediaItem(
                title="..",
                media_id=self.media_id[: self.media_id.rfind("/")],
                media_type=self.media_type_str,
                media_class=self.media_type_str,
                can_browse=True,
                can_search=True,
            )
        except IndexError:
            return None


KODI_BROWSING_BACK: list[KodiMediaEntry] = [
    KodiMediaEntry(
        parent_id="kodi://videos",
        title="..",
        media_type=MediaContentType.URL,
        media_id="kodi://",
        child_media_type=MediaContentType.URL,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id="kodi://tvshows",
        title="..",
        media_type=MediaContentType.URL,
        media_id="kodi://",
        child_media_type=MediaContentType.URL,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id="kodi://music",
        title="..",
        media_type=MediaContentType.URL,
        media_id="kodi://",
        child_media_type=MediaContentType.URL,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id="kodi://pictures",
        title="..",
        media_type=MediaContentType.URL,
        media_id="kodi://",
        child_media_type=MediaContentType.URL,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id="kodi://sources",
        title="..",
        media_type=MediaContentType.URL,
        media_id="kodi://",
        child_media_type=MediaContentType.URL,
        output=KodiObjectType.EMPTY,
    ),
]

KODI_BROWSING: list[KodiMediaEntry] = [
    KodiMediaEntry(
        parent_id=None,
        title="Videos",
        media_type=MediaContentType.MOVIE,
        media_class=MediaClass.MOVIE,
        media_id="kodi://videos",
        child_media_type=MediaContentType.MOVIE,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id=None,
        title="TV Shows",
        media_type=MediaContentType.TV_SHOW,
        media_class=MediaClass.TV_SHOW,
        media_id="kodi://tvshows",
        child_media_type=MediaContentType.TV_SHOW,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id=None,
        title="Music",
        media_type=MediaContentType.MUSIC,
        media_class=MediaClass.MUSIC,
        media_id="kodi://music",
        child_media_type=MediaContentType.MUSIC,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id=None,
        title="Sources",
        media_type=MediaContentType.URL,
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://sources",
        child_media_type=MediaContentType.URL,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id="kodi://videos",
        title="All",
        media_type=MediaContentType.MOVIE,
        media_class=MediaClass.MOVIE,
        media_id="kodi://videos/all",
        command="VideoLibrary.GetMovies",
        arguments={"properties": MOVIE_PROPERTIES},
        child_media_type=MediaContentType.MOVIE,
        output=KodiObjectType.MOVIE,
    ),
    KodiMediaEntry(
        parent_id="kodi://videos",
        title="Now playing",
        media_type=MediaContentType.MOVIE,
        media_class=MediaClass.MOVIE,
        media_id="kodi://videos/current",
        command="VideoLibrary.GetMovies",
        arguments={
            "properties": MOVIE_PROPERTIES,
            "sort": {"method": "lastplayed", "order": "descending"},
            "filter": {"field": "inprogress", "operator": "true", "value": ""},
        },
        child_media_type=MediaContentType.MOVIE,
        output=KodiObjectType.MOVIE,
    ),
    KodiMediaEntry(
        parent_id="kodi://videos",
        title="Recent",
        media_type=MediaContentType.MOVIE,
        media_class=MediaClass.MOVIE,
        media_id="kodi://videos/recent",
        command="VideoLibrary.GetRecentlyAddedMovies",
        arguments={"properties": MOVIE_PROPERTIES},
        child_media_type=MediaContentType.MOVIE,
        output=KodiObjectType.MOVIE,
    ),
    KodiMediaEntry(
        parent_id="kodi://videos",
        title="Genres",
        media_type="kodi://videos/genres",
        media_id="kodi://videos/genres",
        media_class=MediaClass.GENRE,
        command="VideoLibrary.GetGenres",
        arguments={"type": "movie", "properties": ["thumbnail"]},
        child_media_type=MediaContentType.MOVIE,
        output=KodiObjectType.GENRE,
    ),
    KodiMediaEntry(
        parent_id="kodi://videos",
        title="Playlists",
        media_type="kodi://videos/playlists",
        media_id="kodi://videos/playlists",
        media_class=MediaClass.PLAYLIST,
        command="Files.GetDirectory",
        arguments={
            "directory": "special://videoplaylists",
            "media": "files",
            "properties": ["title", "file", "mimetype", "thumbnail"],
        },
        child_media_type=MediaContentType.PLAYLIST,
        output=KodiObjectType.PLAYLIST,
    ),
    KodiMediaEntry(
        parent_id="kodi://videos",
        title="Music videos",
        media_type=MediaContentType.VIDEO,
        media_class=MediaClass.VIDEO,
        media_id="kodi://videos/music",
        command="VideoLibrary.GetMusicVideos",
        arguments={"properties": MOVIE_PROPERTIES},
        child_media_type=MediaContentType.VIDEO,
        output=KodiObjectType.MOVIE,
    ),
    KodiMediaEntry(
        parent_id="kodi://tvshows",
        title="All",
        media_type=MediaContentType.TV_SHOW,
        media_id="kodi://tvshows/all",
        command="VideoLibrary.GetTVShows",
        arguments={"properties": ["art"]},
        child_media_type=MediaContentType.TV_SHOW,
        output=KodiObjectType.TV_SHOW,
    ),
    KodiMediaEntry(
        parent_id="kodi://tvshows",
        title="Now playing",
        media_type=MediaContentType.TV_SHOW,
        media_class=MediaClass.TV_SHOW,
        media_id="kodi://tvshows/current",
        command="VideoLibrary.GetInProgressTVShows",
        arguments={"properties": ["art"]},
        child_media_type=MediaContentType.TV_SHOW,
        output=KodiObjectType.TV_SHOW,
    ),
    KodiMediaEntry(
        parent_id="kodi://tvshows",
        title="Recent",
        media_type=MediaContentType.TV_SHOW,
        media_id="kodi://tvshows/recent",
        media_class=MediaClass.EPISODE,
        command="VideoLibrary.GetRecentlyAddedEpisodes",
        arguments={"properties": EPISODE_PROPERTIES},
        child_media_type=MediaContentType.EPISODE,
        output=KodiObjectType.EPISODE,
    ),
    KodiMediaEntry(
        parent_id="kodi://tvshows",
        title="Genres",
        media_type="kodi://tvshows/genres",
        media_class=MediaClass.GENRE,
        media_id="kodi://tvshows/genres",
        command="VideoLibrary.GetGenres",
        arguments={"type": "tvshow", "properties": ["thumbnail"]},
        child_media_type=MediaContentType.GENRE,
        output=KodiObjectType.GENRE,
    ),
    KodiMediaEntry(
        parent_id="kodi://music",
        title="Albums",
        media_type=MediaContentType.ALBUM,
        media_class=MediaClass.MUSIC,
        media_id="kodi://music/albums",
        command="AudioLibrary.GetAlbums",
        arguments={"properties": ["art", "artist", "albumduration"]},
        child_media_type=MediaContentType.ALBUM,
        output=KodiObjectType.ALBUM,
    ),
    KodiMediaEntry(
        parent_id="kodi://music",
        title="Artists",
        media_type=MediaContentType.ARTIST,
        media_class=MediaClass.ARTIST,
        media_id="kodi://music/artists",
        command="AudioLibrary.GetArtists",
        arguments={"properties": ["thumbnail"]},
        child_media_type=MediaContentType.ARTIST,
        output=KodiObjectType.ARTIST,
    ),
    KodiMediaEntry(
        parent_id="kodi://music",
        title="Genres",
        media_type="kodi://music/genres",
        media_class=MediaClass.GENRE,
        media_id="kodi://music/genres",
        command="AudioLibrary.GetGenres",
        arguments={"properties": ["thumbnail"]},
        child_media_type=MediaContentType.GENRE,
        output=KodiObjectType.GENRE,
    ),
    KodiMediaEntry(
        parent_id="kodi://music",
        title="Playlists",
        media_type="kodi://music/playlists",
        media_id="kodi://music/playlists",
        media_class=MediaClass.PLAYLIST,
        command="Files.GetDirectory",
        arguments={
            "directory": "special://musicplaylists",
            "media": "files",
            "properties": ["title", "file", "mimetype", "thumbnail"],
        },
        child_media_type=MediaContentType.PLAYLIST,
        output=KodiObjectType.PLAYLIST,
    ),
    KodiMediaEntry(
        parent_id="kodi://music",
        title="Songs",
        media_type=MediaContentType.MUSIC,
        media_class=MediaClass.TRACK,
        media_id="kodi://music/songs",
        command="AudioLibrary.GetSongs",
        arguments={"properties": ["art", "duration", "track", "album", "artist"]},
        child_media_type=MediaContentType.MUSIC,
        output=KodiObjectType.SONG,
    ),
    KodiMediaEntry(
        parent_id="kodi://sources",
        title="Videos",
        media_type="kodi://sources/videos",
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://sources/videos",
        command="Files.GetSources",
        arguments={"media": "video"},
        child_media_type=MediaContentType.MOVIE,
        output=KodiObjectType.FILE,
    ),
    KodiMediaEntry(
        parent_id="kodi://sources",
        title="Music",
        media_type="kodi://sources/music",
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://sources/music",
        command="Files.GetSources",
        arguments={"media": "music"},
        child_media_type=MediaContentType.MUSIC,
        output=KodiObjectType.FILE,
    ),
    KodiMediaEntry(
        parent_id="kodi://sources",
        title="Pictures",
        media_type="kodi://sources/pictures",
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://sources/pictures",
        command="Files.GetSources",
        arguments={"media": "pictures"},
        child_media_type=MediaContentType.IMAGE,
        output=KodiObjectType.FILE,
    ),
    KodiMediaEntry(
        parent_id="kodi://sources",
        title="Files",
        media_type="kodi://sources/files",
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://sources/files",
        command="Files.GetSources",
        arguments={"media": "files"},
        child_media_type=MediaContentType.URL,
        output=KodiObjectType.FILE,
    ),
    # ---- PVR (Live TV / Radio) ----
    KodiMediaEntry(
        parent_id=None,
        title="Live TV",
        media_type=MediaContentType.URL,
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://pvr",
        child_media_type=MediaContentType.URL,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id="kodi://pvr",
        title="TV channels",
        media_type=MediaContentType.URL,
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://pvr/tv",
        command="PVR.GetChannelGroups",
        arguments={"channeltype": "tv"},
        child_media_type=MediaContentType.URL,
        output=KodiObjectType.CHANNEL_GROUP,
    ),
    KodiMediaEntry(
        parent_id="kodi://pvr",
        title="Radio channels",
        media_type=MediaContentType.URL,
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://pvr/radio",
        command="PVR.GetChannelGroups",
        arguments={"channeltype": "radio"},
        child_media_type=MediaContentType.URL,
        output=KodiObjectType.CHANNEL_GROUP,
    ),
    # ---- Addons ----
    KodiMediaEntry(
        parent_id=None,
        title="Addons",
        media_type=MediaContentType.URL,
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://addons",
        child_media_type=MediaContentType.URL,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id="kodi://addons",
        title="Video addons",
        media_type=MediaContentType.URL,
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://addons/video",
        command="Addons.GetAddons",
        arguments={
            "content": "video",
            "enabled": True,
            "properties": ["name", "thumbnail", "description"],
        },
        child_media_type=MediaContentType.URL,
        output=KodiObjectType.ADDON,
    ),
    KodiMediaEntry(
        parent_id="kodi://addons",
        title="Music addons",
        media_type=MediaContentType.URL,
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://addons/audio",
        command="Addons.GetAddons",
        arguments={
            "content": "audio",
            "enabled": True,
            "properties": ["name", "thumbnail", "description"],
        },
        child_media_type=MediaContentType.URL,
        output=KodiObjectType.ADDON,
    ),
    # ---- Favorites (pinned shortcuts) ----
    KodiMediaEntry(
        parent_id=None,
        title="Favorites",
        media_type=MediaContentType.URL,
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://favorites",
        child_media_type=MediaContentType.URL,
        output=KodiObjectType.EMPTY,
    ),
]
