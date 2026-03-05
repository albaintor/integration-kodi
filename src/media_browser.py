"""
Browsing definitions used for Kodi integration.

:copyright: (c) 2026 by Albaintor
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import dataclasses
import logging
import time
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Any

from ucapi import StatusCodes

from const import BrowseMediaItem, IKodiDevice, KodiMediaTypes, KodiObjectType

_LOG = logging.getLogger(__name__)

# pylint: disable=C0302


class MediaContent(str, Enum):
    """Media content types supported by UC."""

    ALBUM = "album"
    APP = "app"
    APPS = "apps"
    ARTIST = "artist"
    CHANNEL = "channel"
    CHANNELS = "channels"
    COMPOSER = "composer"
    EPISODE = "episode"
    GAME = "game"
    GENRE = "genre"
    IMAGE = "image"
    MOVIE = "movie"
    MUSIC = "music"
    PLAYLIST = "playlist"
    PODCAST = "podcast"
    RADIO = "radio"
    SEASON = "season"
    TRACK = "track"
    TV_SHOW = "tv_show"
    URL = "url"
    VIDEO = "video"


class MediaClass(str, Enum):
    """Media classes supported by UC."""

    ALBUM = "album"
    APP = "app"
    ARTIST = "artist"
    CHANNEL = "channel"
    COMPOSER = "composer"
    DIRECTORY = "directory"
    EPISODE = "episode"
    GAME = "game"
    GENRE = "genre"
    IMAGE = "image"
    MOVIE = "movie"
    MUSIC = "music"
    PLAYLIST = "playlist"
    PODCAST = "podcast"
    SEASON = "season"
    TRACK = "track"
    TV_SHOW = "tv_show"
    URL = "url"
    VIDEO = "video"


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


def get_artwork(artworks: dict[str, str]) -> str | None:
    """Return best available artwork."""
    if artworks is None:
        return None
    return artworks.get("poster", artworks.get("fanart", artworks.get("thumb", None)))


TRANSLATIONS = {
    "Videos": {"fr": "Vidéos"},
    "TV Shows": {"fr": "Séries"},
    "Music": {"fr": "Musique"},
    "Pictures": {"fr": "Images"},
    "Sources": {"fr": "Sources"},
    "All": {"fr": "Tout"},
    "Recent": {"fr": "Récents"},
    "Currently played": {"fr": "En cours de lecture"},
    "Genres": {"fr": "Genres"},
    "Albums": {"fr": "Albums"},
    "Artists": {"fr": "Artistes"},
    "Files": {"fr": "Fichiers"},
    "Seasons": {"fr": "Saisons"},
    "Media Library": {"fr": "Bibliothèque"},
    "Songs": {"fr": "Chansons"},
}


class MediaBrowser:
    """Media browser."""

    def __init__(self, device: IKodiDevice):
        self._device = device
        self._back_support = True
        if self._back_support:
            self._library_items = KODI_BROWSING_BACK + KODI_BROWSING
        else:
            self._library_items = KODI_BROWSING

    def get_localized(self, value: str) -> str:
        """Return localized value."""
        translation = TRANSLATIONS.get(value)
        if translation is None:
            return value
        translated = translation.get(self._device.app_language_code)
        if translated:
            return translated
        return value

    def get_root_item(self) -> BrowseMediaItem:
        """Build root item."""
        return BrowseMediaItem(
            title=self.get_localized("Media Library"),
            media_id="library",
            media_class=MediaClass.DIRECTORY,
            media_type=MediaContent.URL,
            can_browse=True,
            can_search=True,
            items=[],
        )

    def get_back_item(self, source: str, media_type=MediaContent.URL.value, title="..") -> BrowseMediaItem:
        """Build source item."""
        return BrowseMediaItem(
            title=self.get_localized(title),
            media_id=source,
            media_class=MediaClass.DIRECTORY,
            media_type=media_type,
            can_browse=True,
            can_search=True,
            items=[],
        )

    def get_item_from_file(self, file: dict[str, Any], media_type: str, extract_thumbnail=True) -> BrowseMediaItem:
        """Build item from file."""
        if file.get("filetype", "directory") == "directory":
            return BrowseMediaItem(
                title=file.get("label", ""),
                media_id=file.get("file", ""),
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
            title=file.get("label", ""),
            media_id=file.get("file", ""),
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

    def get_item_from_movie(self, movie: dict[str, Any]) -> BrowseMediaItem:
        """Build item from movie."""
        art = get_artwork(movie.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        return BrowseMediaItem(
            title=movie.get("label", ""),
            media_id=str(movie.get("movieid", 0)),
            media_class=MediaClass.MOVIE,
            media_type=MediaContent.MOVIE,
            can_browse=False,
            can_search=True,
            can_play=True,
            thumbnail=art,
        )

    def get_item_from_episode(self, episode: dict[str, Any]) -> BrowseMediaItem:
        """Build item from episode."""
        art = get_artwork(episode.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        return BrowseMediaItem(
            title=episode.get("label", ""),
            media_id=str(episode.get("file", "")),
            media_class=MediaClass.EPISODE,
            media_type=MediaContent.EPISODE,
            can_browse=False,
            can_search=True,
            can_play=True,
            thumbnail=art,
        )

    def get_item_from_tvshow(self, show: dict[str, Any]) -> BrowseMediaItem:
        """Build item from TV Show."""
        art = get_artwork(show.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        return BrowseMediaItem(
            title=show.get("label", ""),
            media_id=str(show.get("tvshowid", 0)),
            media_class=MediaClass.TV_SHOW,
            media_type=MediaContent.TV_SHOW,
            can_browse=True,
            can_search=True,
            thumbnail=art,
        )

    def get_item_from_season(self, show_id: int, season: dict[str, Any]) -> BrowseMediaItem:
        """Build item from TV Show season."""
        art = get_artwork(season.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        return BrowseMediaItem(
            title=season.get("label", ""),
            media_id=str(show_id) + ";" + str(season.get("season", 0)),
            media_class=MediaClass.SEASON,
            media_type=MediaContent.SEASON,
            can_browse=True,
            can_search=True,
            thumbnail=art,
        )

    @staticmethod
    def get_parent_item_tvshow(show_id: int) -> BrowseMediaItem:
        """Build item from TV Show."""
        return BrowseMediaItem(
            title="..",
            media_id=str(show_id),
            media_class=MediaClass.TV_SHOW,
            media_type=MediaContent.TV_SHOW,
            can_browse=True,
            can_search=True,
        )

    def get_item_from_album(self, album: dict[str, Any]) -> BrowseMediaItem:
        """Build item from Album."""
        art = get_artwork(album.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        return BrowseMediaItem(
            title=album.get("label", ""),
            media_id=str(album.get("albumid", 0)),
            media_class=MediaClass.ALBUM,
            media_type=MediaContent.ALBUM,
            can_browse=True,
            can_search=True,
            thumbnail=art,
        )

    def get_item_from_artist(self, artist: dict[str, Any]) -> BrowseMediaItem:
        """Build item from Artist."""
        art = get_artwork(artist.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        return BrowseMediaItem(
            title=artist.get("label", ""),
            media_id=str(artist.get("artistid", 0)),
            media_class=MediaClass.ARTIST,
            media_type=MediaContent.ARTIST,
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
            media_type=MediaContent.MUSIC,
            can_browse=False,
            can_search=True,
            can_play=True,
            thumbnail=art,
        )

    def get_item_from_genre(self, media_type: str, genre: dict[str, Any]) -> BrowseMediaItem:
        """Build item from TV Show."""
        art = get_artwork(genre.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        return BrowseMediaItem(
            title=genre.get("label", ""),
            media_id=str(genre.get("genreid", 0)),
            media_class=MediaClass.GENRE,
            media_type=media_type,
            can_browse=True,
            can_search=True,
            thumbnail=art,
        )

    @staticmethod
    def get_sorting(sorting: str) -> dict[str, str]:
        """Build sorting method."""
        param = sorting.split(" ")
        result = {"method": param[0]}
        if len(param) > 1:
            result["order"] = param[1]
        return result

    async def browse_media(
        self, media_id: str | None, media_type: str | None, paging: dict[str, Any] | None
    ) -> tuple[BrowseMediaItem, dict[str, Any]] | None:
        """Browse media."""
        # pylint: disable=R0914,R1702,R0911,R0915
        try:
            if paging is None:
                paging = {"page": 1, "limit": 10}
            else:
                paging = paging.copy()

            # Return library root
            if media_id is None or media_id == "" or media_id == "kodi://":
                items = [x.get_media_item() for x in self._library_items if x.parent_id is None]
                for item in items:
                    item.title = self.get_localized(item.title)
                paging["count"] = len(items)
                item = self.get_root_item()
                item.title = self.get_localized(item.title)
                item.items = items
                return item, paging

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
                if entry is not None:
                    item = entry.get_media_item()
                    item.items = [x.get_media_item() for x in entries]
                    # item.items.insert(0, entry.get_parent_item())
                    paging["count"] = len(entries)
                else:
                    item = self.get_root_item()
                    item.items = [x.get_media_item() for x in entries]
                    paging["count"] = len(entries)
                return item, paging

            # Given media_id is defined in the library items with a command to extract sub-items
            if entry is not None and entry.command is not None:
                entry.title = self.get_localized(entry.title)
                arguments = entry.arguments.copy() if entry.arguments else {}
                item = entry.get_media_item()
                limit = paging.get("limit")
                end = paging.get("page") * limit
                if self._back_support and paging.get("page") == 1:
                    end -= 1
                arguments["limits"] = {
                    "start": (paging.get("page") - 1) * limit,
                    "end": end,
                }
                if (
                    media_type == MediaContent.MOVIE.value
                    and self._device.device_config.browsing_video_sort
                    and arguments.get("sort") is None
                ):
                    arguments["sort"] = MediaBrowser.get_sorting(self._device.device_config.browsing_video_sort)
                elif (
                    media_type == MediaContent.ALBUM.value
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

                _LOG.debug("[%s] Browsing command %s %s", self._device.device_config.address, entry.command, arguments)
                data = await self._device.client.call_method(entry.command, **arguments)
                paging["count"] = data.get("limits", {}).get("total", 0)
                if self._back_support:
                    paging["count"] = paging["count"] + 1

                if entry.output == KodiObjectType.FILE:
                    # media_type = kodi://sources/<videos|music|pictures|files>
                    # Each files have following format : smb://...|nfs://...|multipath://...
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(self.get_back_item("kodi://sources"))
                    for file in data.get("files", data.get("sources", [])):
                        item.items.append(self.get_item_from_file(file, media_type, False))
                elif entry.output == KodiObjectType.MOVIE:
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(self.get_back_item("kodi://videos", MediaContent.MOVIE.value))
                    for movie in data.get("movies", []):
                        item.items.append(self.get_item_from_movie(movie))
                elif entry.output == KodiObjectType.EPISODE:
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(self.get_back_item("kodi://tvshows", MediaContent.TV_SHOW.value))
                    for episode in data.get("episodes", []):
                        item.items.append(self.get_item_from_episode(episode))
                elif entry.output == KodiObjectType.TV_SHOW:
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(self.get_back_item("kodi://tvshows", MediaContent.TV_SHOW.value))
                    for show in data.get("tvshows", []):
                        item.items.append(self.get_item_from_tvshow(show))
                elif entry.output == KodiObjectType.EPISODE:
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(self.get_back_item("kodi://tvshows", MediaContent.TV_SHOW.value))
                    for episode in data.get("episodes", []):
                        item.items.append(self.get_item_from_episode(episode))
                elif entry.output == KodiObjectType.ALBUM:
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(self.get_back_item("kodi://music", MediaContent.MUSIC.value))
                    for album in data.get("albums", []):
                        item.items.append(self.get_item_from_album(album))
                elif entry.output == KodiObjectType.GENRE:
                    if self._back_support and paging.get("page") == 1:
                        try:
                            parent_media_id = media_type[: media_type.rfind("/")]
                            item.items.append(self.get_back_item(parent_media_id, media_type))
                        # pylint: disable = W0718
                        except Exception:
                            pass
                    for genre in data.get("genres", []):
                        item.items.append(self.get_item_from_genre(media_type, genre))
                elif entry.output == KodiObjectType.ARTIST:
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(self.get_back_item("kodi://music", MediaContent.MUSIC.value))
                    for artist in data.get("artists", []):
                        item.items.append(self.get_item_from_artist(artist))
                elif entry.output == KodiObjectType.SONG:
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(self.get_back_item("kodi://music", MediaContent.MUSIC.value))
                    for song in data.get("songs", []):
                        item.items.append(self.get_item_from_song(song))
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
                if media_type.startswith("kodi://sources"):
                    back_buttons = 0
                    item = self.get_root_item()
                    limit = paging.get("limit")
                    end = paging.get("page") * limit
                    media = KodiMediaTypes.VIDEOS.value
                    for key, kodi_type in SOURCE_MEDIA_TYPES_MAPPING.items():
                        if media_type.startswith(key):
                            media = kodi_type
                            break
                    if self._back_support and paging.get("page") == 1:
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
                            "start": (paging.get("page") - 1) * limit,
                            "end": end,
                        },
                    }
                    if self._device.device_config.browsing_files_sort:
                        arguments["sort"] = MediaBrowser.get_sorting(self._device.device_config.browsing_files_sort)
                    # Apply media filter on pictures only
                    if media == KodiMediaTypes.PICTURES.value:
                        arguments["media"] = media

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
                            item.items.append(self.get_item_from_file(file, media_type, extract_thumbnail))
                        paging["count"] = data.get("limits", {}).get("total", 0)
                        if self._back_support:
                            paging["count"] = paging["count"] + back_buttons
                    return item, paging
                if media_type == MediaContent.TV_SHOW.value:
                    item = self.get_root_item()
                    limit = paging.get("limit")
                    end = paging.get("page") * limit
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(self.get_back_item("kodi://tvshows", media_type))
                        end -= 1
                    arguments = {
                        "properties": ["art", "season"],
                        "tvshowid": int(media_id),
                        "limits": {
                            "start": (paging.get("page") - 1) * limit,
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
                    paging["count"] = seasons.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging["count"] = paging["count"] + 1
                    for season in seasons["seasons"]:
                        item.items.append(self.get_item_from_season(int(media_id), season))
                elif media_type == MediaContent.SEASON.value:
                    (show_id, season) = media_id.split(";")
                    item = self.get_root_item()
                    limit = paging.get("limit")
                    end = paging.get("page") * limit
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(MediaBrowser.get_parent_item_tvshow(int(show_id)))
                        end -= 1
                    arguments = {
                        "properties": ["art", "file"],
                        "tvshowid": int(show_id),
                        "season": int(season),
                        "limits": {
                            "start": (paging.get("page") - 1) * limit,
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
                    item = self.get_root_item()
                    paging["count"] = episodes.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging["count"] = paging["count"] + 1
                    for episode in episodes["episodes"]:
                        item.items.append(self.get_item_from_episode(episode))
                elif media_type == MediaContent.ALBUM.value:
                    item = self.get_root_item()
                    limit = paging.get("limit")
                    end = paging.get("page") * limit
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(self.get_back_item("kodi://music", MediaContent.MUSIC.value))
                        end -= 1
                    arguments = {
                        "properties": ["art", "duration", "track"],
                        "filter": {"albumid": int(media_id)},
                        "limits": {
                            "start": (paging.get("page") - 1) * limit,
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
                    paging["count"] = songs.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging["count"] = paging["count"] + 1
                    for song in songs["songs"]:
                        item.items.append(self.get_item_from_song(song, media_id))
                elif media_type == MediaContent.ARTIST.value:
                    item = self.get_root_item()
                    limit = paging.get("limit")
                    end = paging.get("page") * limit
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(self.get_back_item("kodi://music", MediaContent.MUSIC.value))
                        end -= 1
                    arguments = {
                        "properties": ["art"],
                        "filter": {"artistid": int(media_id)},
                        "limits": {
                            "start": (paging.get("page") - 1) * limit,
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
                    paging["count"] = albums.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging["count"] = paging["count"] + 1
                    for album in albums["albums"]:
                        item.items.append(self.get_item_from_album(album))
                elif media_type == "kodi://videos/genres":
                    item = self.get_root_item()
                    limit = paging.get("limit")
                    end = paging.get("page") * limit
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(self.get_back_item("kodi://videos", MediaContent.MOVIE.value))
                        end -= 1
                    arguments = {
                        "properties": ["resume", "art"],
                        "filter": {"genreid": int(media_id)},
                        "limits": {
                            "start": (paging.get("page") - 1) * limit,
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
                    paging["count"] = medias.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging["count"] = paging["count"] + 1
                    for media in medias["movies"]:
                        item.items.append(self.get_item_from_movie(media))
                elif media_type == "kodi://tvshows/genres":
                    item = self.get_root_item()
                    limit = paging.get("limit")
                    end = paging.get("page") * limit
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(self.get_back_item("kodi://tvshows", MediaContent.TV_SHOW.value))
                        end -= 1
                    arguments = {
                        "properties": ["art"],
                        "filter": {"genreid": int(media_id)},
                        "limits": {
                            "start": (paging.get("page") - 1) * limit,
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
                    paging["count"] = medias.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging["count"] = paging["count"] + 1
                    for media in medias["tvshows"]:
                        item.items.append(self.get_item_from_tvshow(media))
                elif media_type == "kodi://music/genres":
                    item = self.get_root_item()
                    limit = paging.get("limit")
                    end = paging.get("page") * limit
                    if self._back_support and paging.get("page") == 1:
                        item.items.append(self.get_back_item("kodi://music", MediaContent.MUSIC.value))
                        end -= 1
                    arguments = {
                        "properties": ["art"],
                        "filter": {"genreid": int(media_id)},
                        "limits": {
                            "start": (paging.get("page") - 1) * limit,
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
                    paging["count"] = medias.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging["count"] = paging["count"] + 1
                    for album in medias.get("albums", []):
                        item.items.append(self.get_item_from_album(album))
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
        return None

    async def play_media(self, params: dict[str, Any]) -> StatusCodes:
        """Play given media id."""
        media_id = params.get("media_id")
        media_type = params.get("media_type")
        # TODO handle action (enqueue, play...)
        # action = params.get("action")
        if media_id is None or media_type is None:
            return StatusCodes.BAD_REQUEST
        if media_type == MediaContent.MOVIE.value:
            _LOG.debug("[%s] Playing movie id %s", self._device.device_config.address, media_id)
            await self._device.server.Player.Open(**{"item": {"movieid": int(media_id)}})
        if media_type == MediaContent.EPISODE.value:
            _LOG.debug("[%s] Playing media id %s", self._device.device_config.address, media_id)
            await self._device.server.Player.Open(**{"item": {"file": media_id}})
        elif media_type == MediaContent.MUSIC.value:
            media_data = media_id.split(";")
            if len(media_data) == 1:
                arguments = {"item": {"songid": int(media_data[0])}}
                _LOG.debug("[%s] Playing music %s", self._device.device_config.address, arguments)
                await self._device.server.Player.Open(**{"item": {"songid": int(media_data[0])}})
            else:
                song_id = int(media_data[0])
                album_id = int(media_data[1])
                await self._device.server.Playlist.Clear(**{"playlistid": 0})
                await self._device.server.Playlist.Add(**{"playlistid": 0, "item": {"albumid": album_id}})
                playlist = await self._device.client.call_method(
                    "AudioLibrary.GetSongs",
                    **{"filter": {"albumid": album_id}, "properties": ["track"], "sort": {"method": "track"}},
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
        elif media_type == MediaContent.ALBUM.value:
            _LOG.debug("[%s] Playing album %s", self._device.device_config.address, media_id)
            await self._device.server.Player.Open(**{"item": {"albumid": int(media_id)}})
        elif media_type == MediaContent.URL.value or media_type.startswith("kodi://sources"):
            _LOG.debug("[%s] Playing file %s", self._device.device_config.address, media_id)
            await self._device.server.Player.Open(**{"item": {"file": media_id}})
        return StatusCodes.OK


@dataclass
class KodiMediaEntry:
    """Media entry for browsing media."""

    title: str
    media_type: MediaContent | str
    child_media_type: MediaContent
    media_id: str
    output: KodiObjectType
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

    def get_media_item(self) -> BrowseMediaItem:
        """Build media item."""
        return BrowseMediaItem(
            title=self.title,
            media_id=self.media_id,
            media_type=self.media_type,
            media_class=self.media_type,
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
                media_type=self.media_type,
                media_class=self.media_type,
                can_browse=True,
                can_search=True,
            )
        except IndexError:
            return None


KODI_BROWSING_BACK: list[KodiMediaEntry] = [
    KodiMediaEntry(
        parent_id="kodi://videos",
        title="..",
        media_type=MediaContent.URL,
        media_id="kodi://",
        child_media_type=MediaContent.URL,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id="kodi://tvshows",
        title="..",
        media_type=MediaContent.URL,
        media_id="kodi://",
        child_media_type=MediaContent.URL,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id="kodi://music",
        title="..",
        media_type=MediaContent.URL,
        media_id="kodi://",
        child_media_type=MediaContent.URL,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id="kodi://pictures",
        title="..",
        media_type=MediaContent.URL,
        media_id="kodi://",
        child_media_type=MediaContent.URL,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id="kodi://sources",
        title="..",
        media_type=MediaContent.URL,
        media_id="kodi://",
        child_media_type=MediaContent.URL,
        output=KodiObjectType.EMPTY,
    ),
]

KODI_BROWSING: list[KodiMediaEntry] = [
    KodiMediaEntry(
        parent_id=None,
        title="Videos",
        media_type=MediaContent.MOVIE,
        media_id="kodi://videos",
        child_media_type=MediaContent.MOVIE,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id=None,
        title="TV Shows",
        media_type=MediaContent.TV_SHOW,
        media_id="kodi://tvshows",
        child_media_type=MediaContent.TV_SHOW,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id=None,
        title="Music",
        media_type=MediaContent.MUSIC,
        media_id="kodi://music",
        child_media_type=MediaContent.MUSIC,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id=None,
        title="Sources",
        media_type=MediaContent.URL,
        media_id="kodi://sources",
        child_media_type=MediaContent.URL,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id="kodi://videos",
        title="All",
        media_type=MediaContent.MOVIE,
        media_id="kodi://videos/all",
        command="VideoLibrary.GetMovies",
        arguments={"properties": ["art"]},
        child_media_type=MediaContent.MOVIE,
        output=KodiObjectType.MOVIE,
    ),
    KodiMediaEntry(
        parent_id="kodi://videos",
        title="Currently played",
        media_type=MediaContent.MOVIE,
        media_id="kodi://videos/current",
        command="VideoLibrary.GetMovies",
        arguments={
            "properties": ["resume", "art"],
            "sort": {"method": "lastplayed", "order": "descending"},
            "filter": {"field": "inprogress", "operator": "true", "value": ""},
        },
        child_media_type=MediaContent.MOVIE,
        output=KodiObjectType.MOVIE,
    ),
    KodiMediaEntry(
        parent_id="kodi://videos",
        title="Recent",
        media_type=MediaContent.MOVIE,
        media_id="kodi://videos/recent",
        command="VideoLibrary.GetRecentlyAddedMovies",
        arguments={"properties": ["art"]},
        child_media_type=MediaContent.MOVIE,
        output=KodiObjectType.MOVIE,
    ),
    KodiMediaEntry(
        parent_id="kodi://videos",
        title="Genres",
        media_type="kodi://videos/genres",
        media_id="kodi://videos/genres",
        command="VideoLibrary.GetGenres",
        arguments={"type": "movie", "properties": ["thumbnail"]},
        child_media_type=MediaContent.MOVIE,
        output=KodiObjectType.GENRE,
    ),
    KodiMediaEntry(
        parent_id="kodi://tvshows",
        title="All",
        media_type=MediaContent.TV_SHOW,
        media_id="kodi://tvshows/all",
        command="VideoLibrary.GetTVShows",
        arguments={"properties": ["art"]},
        child_media_type=MediaContent.TV_SHOW,
        output=KodiObjectType.TV_SHOW,
    ),
    KodiMediaEntry(
        parent_id="kodi://tvshows",
        title="Currently played",
        media_type=MediaContent.TV_SHOW,
        media_id="kodi://tvshows/current",
        command="VideoLibrary.GetInProgressTVShows",
        arguments={"properties": ["art"]},
        child_media_type=MediaContent.TV_SHOW,
        output=KodiObjectType.TV_SHOW,
    ),
    KodiMediaEntry(
        parent_id="kodi://tvshows",
        title="Recent",
        media_type=MediaContent.TV_SHOW,
        media_id="kodi://tvshows/recent",
        command="VideoLibrary.GetRecentlyAddedEpisodes",
        arguments={"properties": ["art", "file"]},
        child_media_type=MediaContent.EPISODE,
        output=KodiObjectType.EPISODE,
    ),
    KodiMediaEntry(
        parent_id="kodi://tvshows",
        title="Genres",
        media_type="kodi://tvshows/genres",
        media_id="kodi://tvshows/genres",
        command="VideoLibrary.GetGenres",
        arguments={"type": "tvshow", "properties": ["thumbnail"]},
        child_media_type=MediaContent.GENRE,
        output=KodiObjectType.GENRE,
    ),
    KodiMediaEntry(
        parent_id="kodi://music",
        title="Albums",
        media_type=MediaContent.ALBUM,
        media_id="kodi://music/albums",
        command="AudioLibrary.GetAlbums",
        arguments={"properties": ["art"]},
        child_media_type=MediaContent.ALBUM,
        output=KodiObjectType.ALBUM,
    ),
    KodiMediaEntry(
        parent_id="kodi://music",
        title="Artists",
        media_type=MediaContent.ARTIST,
        media_id="kodi://music/artists",
        command="AudioLibrary.GetArtists",
        arguments={"properties": ["thumbnail"]},
        child_media_type=MediaContent.ARTIST,
        output=KodiObjectType.ARTIST,
    ),
    KodiMediaEntry(
        parent_id="kodi://music",
        title="Genres",
        media_type="kodi://music/genres",
        media_id="kodi://music/genres",
        command="AudioLibrary.GetGenres",
        arguments={"properties": ["thumbnail"]},
        child_media_type=MediaContent.GENRE,
        output=KodiObjectType.GENRE,
    ),
    KodiMediaEntry(
        parent_id="kodi://music",
        title="Songs",
        media_type=MediaContent.MUSIC,
        media_id="kodi://music/songs",
        command="AudioLibrary.GetSongs",
        arguments={"properties": ["art", "duration", "track"]},
        child_media_type=MediaContent.MUSIC,
        output=KodiObjectType.SONG,
    ),
    KodiMediaEntry(
        parent_id="kodi://sources",
        title="Videos",
        media_type="kodi://sources/videos",
        media_id="kodi://sources/videos",
        command="Files.GetSources",
        arguments={"media": "video"},
        child_media_type=MediaContent.MOVIE,
        output=KodiObjectType.FILE,
    ),
    KodiMediaEntry(
        parent_id="kodi://sources",
        title="Music",
        media_type="kodi://sources/music",
        media_id="kodi://sources/music",
        command="Files.GetSources",
        arguments={"media": "music"},
        child_media_type=MediaContent.MUSIC,
        output=KodiObjectType.FILE,
    ),
    KodiMediaEntry(
        parent_id="kodi://sources",
        title="Pictures",
        media_type="kodi://sources/pictures",
        media_id="kodi://sources/pictures",
        command="Files.GetSources",
        arguments={"media": "pictures"},
        child_media_type=MediaContent.IMAGE,
        output=KodiObjectType.FILE,
    ),
    KodiMediaEntry(
        parent_id="kodi://sources",
        title="Files",
        media_type="kodi://sources/files",
        media_id="kodi://sources/files",
        command="Files.GetSources",
        arguments={"media": "files"},
        child_media_type=MediaContent.URL,
        output=KodiObjectType.FILE,
    ),
]
