"""
Browsing definitions used for Kodi integration.

:copyright: (c) 2026 by Albaintor
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import dataclasses
import logging
import os
import time
from dataclasses import dataclass, field, fields
from typing import Any
from urllib.parse import quote, unquote

from ucapi import StatusCodes
from ucapi.api_definitions import (
    MediaClass,
    Pagination,
    PagingOptions,
    SearchMediaFilter,
)

from const import (
    BrowseMediaItem,
    IKodiDevice,
    KodiMediaSearchMode,
    KodiMediaTypes,
    KodiObjectType,
    MediaContent,
)
from translations import TRANSLATIONS

_LOG = logging.getLogger(__name__)

# pylint: disable=C0302,R0801,R0917


MEDIA_CONTENT_LABELS = {
    MediaContent.MOVIE: "Videos",
    MediaContent.TV_SHOW: "TV Shows",
    MediaContent.ALBUM: "Albums",
    MediaContent.ARTIST: "Artists",
    MediaContent.MUSIC: "Music",
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
    return artworks.get("poster", artworks.get("fanart", artworks.get("album.thumb", artworks.get("thumb", None))))


def get_element(element: Any | None) -> str | None:
    """Return best available element."""
    if element is None:
        return None
    if isinstance(element, list):
        return element[0] if len(element) > 0 else None
    return element


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
        self, media_class=MediaClass.DIRECTORY.value, media_type=MediaContent.URL.value
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
        self, source: str, media_type=MediaContent.URL.value, title="..", media_class: MediaClass = MediaClass.DIRECTORY
    ) -> BrowseMediaItem:
        """Build source item."""
        return BrowseMediaItem(
            title=self.get_localized(title),
            media_id=source,
            media_class=media_class.value,
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
                media_class=MediaClass.DIRECTORY.value,
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
            media_class=MediaClass.VIDEO.value,
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
        duration = data.get("duration", data.get("runtime", None))
        if duration is None or duration == 0:
            duration = data.get("resume", {}).get("total", None)
        if duration == 0.0:
            duration = None
        return duration

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
            media_class=MediaClass.MOVIE.value,
            media_type=MediaContent.MOVIE.value,
            can_play=True,
            thumbnail=art,
            duration=MediaBrowser.get_duration(movie),
        )

    def get_item_from_episode(self, episode: dict[str, Any]) -> BrowseMediaItem:
        """Build item from episode."""
        art = get_artwork(episode.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        media_id = str(episode.get("file", ""))
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
            media_class=MediaClass.EPISODE.value,
            media_type=MediaContent.EPISODE.value,
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
            media_class=MediaClass.TV_SHOW.value,
            media_type=MediaContent.TV_SHOW.value,
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
            media_class=MediaClass.SEASON.value,
            media_type=MediaContent.SEASON.value,
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
        return BrowseMediaItem(
            title=album.get("label", ""),
            media_id=media_id,
            media_class=MediaClass.ALBUM.value,
            media_type=MediaContent.ALBUM.value,
            can_browse=True,
            can_search=True,
            thumbnail=art,
            album=album.get("label", None),
            artist=artist,
            duration=album.get("albumduration", None),
        )

    def get_item_from_artist(self, artist: dict[str, Any], parent_id: str) -> BrowseMediaItem:
        """Build item from Artist."""
        art = get_artwork(artist.get("art", None))
        if art:
            art = self.get_artwork_url(art)
        media_id = str(artist.get("artistid", 0))
        if parent_id:
            media_id = parent_id + "/" + media_id
        return BrowseMediaItem(
            title=artist.get("label", ""),
            media_id=media_id,
            media_class=MediaClass.ARTIST.value,
            media_type=MediaContent.ARTIST.value,
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
            media_class=MediaClass.MUSIC.value,
            media_type=MediaContent.MUSIC.value,
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
            media_class=MediaClass.GENRE.value,
            media_type=media_type + "/" + quote(genre.get("label", "")),
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
        self, media_id: str | None, media_type: str | None, paging: PagingOptions | None
    ) -> tuple[BrowseMediaItem, Pagination] | None:
        """Browse media."""
        # pylint: disable=R0914,R1702,R0911,R0915,W1405
        try:
            if paging is None:
                paging = Pagination(page=1, limit=10, count=0)
            else:
                paging = Pagination(page=paging.page, limit=paging.limit, count=0)

            # Return library root
            if media_id is None or media_id == "" or media_id == "kodi://":
                items: list[BrowseMediaItem] = [x.get_media_item() for x in self._library_items if x.parent_id is None]
                # Add currently playing playlist if any
                current_playlist = await self._device.get_current_playlist()
                if current_playlist and current_playlist.position >= 0:
                    art = get_artwork(current_playlist.playlist["items"][current_playlist.position].get("art", None))
                    if art:
                        art = self.get_artwork_url(art)

                    items.insert(
                        0,
                        BrowseMediaItem(
                            title=f"{self.get_localized('Now playing')} "
                            f"({current_playlist.playlist['items'][current_playlist.position].get('label', '')})",
                            media_class=MediaClass.PLAYLIST.value,
                            media_type=MediaClass.PLAYLIST.value,
                            media_id="kodi://playing",
                            thumbnail=art,
                            can_browse=True,
                            duration=current_playlist.playlist["items"][current_playlist.position].get(
                                "duration", None
                            ),
                            album=current_playlist.playlist["items"][current_playlist.position].get("album", None),
                            artist=get_element(
                                current_playlist.playlist["items"][current_playlist.position].get("artist", None)
                            ),
                        ),
                    )

                for item in items:
                    item.title = self.get_localized(item.title)

                paging.count = len(items)
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
                    item.title = self.get_localized(item.title)
                    item.items = [x.get_media_item() for x in entries]
                    # item.items.insert(0, entry.get_parent_item())
                    paging.count = len(entries)
                else:
                    item = self.get_root_item()
                    item.items = [x.get_media_item() for x in entries]
                    paging.count = len(entries)
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
                    media_type in [MediaContent.MOVIE.value, MediaContent.VIDEO.value]
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
                paging.count = data.get("limits", {}).get("total", 0)
                if self._back_support:
                    paging.count = paging.count + 1

                if entry.output == KodiObjectType.FILE:
                    # media_type = kodi://sources/<videos|music|pictures|files>
                    # Each files have following format : smb://...|nfs://...|multipath://...
                    if self._back_support and paging.page == 1:
                        item.items.append(self.get_back_item("kodi://sources"))
                    for file in data.get("files", data.get("sources", [])):
                        item.items.append(self.get_item_from_file(file, media_type, False))
                elif entry.output == KodiObjectType.MOVIE:
                    if self._back_support and paging.page == 1:
                        item.items.append(self.get_back_item("kodi://videos", MediaContent.MOVIE.value))
                    if entry.media_id == "kodi://videos/music":
                        for movie in data.get("musicvideos", []):
                            item.items.append(self.get_item_from_movie(movie, media_id))
                    else:
                        for movie in data.get("movies", []):
                            item.items.append(self.get_item_from_movie(movie, media_id))
                elif entry.output == KodiObjectType.EPISODE:
                    if self._back_support and paging.page == 1:
                        item.items.append(self.get_back_item("kodi://tvshows", MediaContent.TV_SHOW.value))
                    for episode in data.get("episodes", []):
                        item.items.append(self.get_item_from_episode(episode))
                elif entry.output == KodiObjectType.TV_SHOW:
                    if self._back_support and paging.page == 1:
                        item.items.append(self.get_back_item("kodi://tvshows", MediaContent.TV_SHOW.value))
                    for show in data.get("tvshows", []):
                        item.items.append(self.get_item_from_tvshow(show, media_id))
                elif entry.output == KodiObjectType.EPISODE:
                    if self._back_support and paging.page == 1:
                        item.items.append(self.get_back_item("kodi://tvshows", MediaContent.TV_SHOW.value))
                    for episode in data.get("episodes", []):
                        item.items.append(self.get_item_from_episode(episode))
                elif entry.output == KodiObjectType.ALBUM:
                    if self._back_support and paging.page == 1:
                        item.items.append(self.get_back_item("kodi://music", MediaContent.MUSIC.value))
                    for album in data.get("albums", []):
                        item.items.append(self.get_item_from_album(album, media_id))
                elif entry.output == KodiObjectType.GENRE:
                    if self._back_support and paging.page == 1:
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
                    if self._back_support and paging.page == 1:
                        item.items.append(self.get_back_item("kodi://music", MediaContent.MUSIC.value))
                    for artist in data.get("artists", []):
                        item.items.append(self.get_item_from_artist(artist, media_id))
                elif entry.output == KodiObjectType.SONG:
                    if self._back_support and paging.page == 1:
                        item.items.append(self.get_back_item("kodi://music", MediaContent.MUSIC.value))
                    for song in data.get("songs", []):
                        item.items.append(self.get_item_from_song(song, media_id))
                elif entry.output == KodiObjectType.PLAYLIST:
                    if self._back_support and paging.page == 1:
                        item.items.append(self.get_back_item(entry.parent_id))
                    for media in data.get("files", []):
                        # Strip off extension file
                        media["label"] = os.path.splitext(media.get("label"))[0]
                        media["filetype"] = "file"
                        item.items.append(self.get_item_from_file(media, media_id, extract_thumbnail=False))
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
                            item.items.append(self.get_item_from_file(file, media_type, extract_thumbnail))
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

                if media_type == MediaContent.TV_SHOW.value:
                    item = self.get_root_item(MediaContent.SEASON.value, MediaContent.SEASON.value)
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
                        try:
                            item.title = seasons["seasons"][0]["showtitle"]
                        except Exception:  # pylint: disable = W0718
                            pass
                    paging.count = seasons.get("limits", {}).get("total", 0)
                    if self._back_support:
                        paging.count = paging.count + 1
                    for season in seasons["seasons"]:
                        item.items.append(self.get_item_from_season(season, media_id))
                elif media_type == MediaContent.SEASON.value:
                    show_id = parent_id.rsplit("/", 1)[-1]
                    season = real_media_id
                    item = self.get_root_item(MediaContent.EPISODE.value, MediaContent.EPISODE.value)
                    limit = paging.limit
                    end = paging.page * limit
                    if self._back_support and paging.page == 1:
                        # "kodi://tvshows/genres/5/32/1"
                        MediaBrowser.get_parent_item_tvshow(parent_id, MediaContent.TV_SHOW.value)
                        item.items.append(MediaBrowser.get_parent_item_tvshow(parent_id, MediaContent.TV_SHOW.value))
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
                    for episode in episodes["episodes"]:
                        item.items.append(self.get_item_from_episode(episode))
                elif media_type == MediaContent.ALBUM.value:
                    item = self.get_root_item(MediaContent.MUSIC.value, MediaContent.MUSIC.value)
                    limit = paging.limit
                    end = paging.page * limit
                    if self._back_support and paging.page == 1:
                        if parent_id.startswith("kodi://music/artists"):
                            parent_media_class = MediaClass.ARTIST
                            parent_media_type = MediaContent.ARTIST
                        elif parent_id.startswith("kodi://music/genres"):
                            parent_id = "kodi://music/genres"
                            parent_media_class = MediaClass.GENRE
                            parent_media_type = "kodi://music/genres"
                        else:
                            parent_media_class = MediaClass.ALBUM
                            parent_media_type = MediaContent.ALBUM
                        item.items.append(
                            self.get_back_item(
                                parent_id if parent_id else "kodi://music",
                                parent_media_type.value,
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
                elif media_type == MediaContent.ARTIST.value:
                    item = self.get_root_item(MediaContent.ALBUM.value, MediaContent.ALBUM.value)
                    limit = paging.limit
                    end = paging.page * limit
                    if self._back_support and paging.page == 1:
                        item.items.append(
                            self.get_back_item(parent_id if parent_id else "kodi://music", MediaContent.MUSIC.value)
                        )
                        end -= 1
                    arguments = {
                        "properties": ["art", "artist", "albumduration"],
                        "filter": {"artistid": int(real_media_id)},
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
                    item = self.get_root_item(MediaContent.MOVIE.value, MediaContent.MOVIE.value)
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
                    item = self.get_root_item(MediaContent.TV_SHOW.value, MediaContent.TV_SHOW.value)
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
                    item = self.get_root_item(MediaContent.ALBUM.value, MediaContent.ALBUM.value)
                    limit = paging.limit
                    end = paging.page * limit
                    if self._back_support and paging.page == 1:
                        item.items.append(
                            self.get_back_item(parent_id if parent_id else "kodi://music", MediaContent.MUSIC.value)
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
                elif media_type == MediaContent.PLAYLIST.value:
                    item = self.get_root_item(MediaContent.PLAYLIST.value, MediaContent.PLAYLIST.value)
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
                            item.items.append(
                                BrowseMediaItem(
                                    title=(
                                        playlist_item.get("label", "")
                                        if position != current_playlist.position or not tag_current
                                        else f">> {playlist_item.get('label', '')} <<"
                                    ),
                                    media_class=media_type.value,
                                    media_type=MediaContent.PLAYLIST.value,
                                    media_id=f"kodi://playlist/{current_playlist.playlist_id}/{position}",
                                    can_play=True,
                                    can_search=True,
                                    subtitle=str(playlist_item.get("year")) if playlist_item.get("year") else None,
                                    album=playlist_item.get("album", None),
                                    artist=get_element(playlist_item.get("artist", None)),
                                    duration=playlist_item.get("duration", None),
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
            paging = Pagination(page=1, limit=10, count=0)
        else:
            paging = Pagination(page=paging.page, limit=paging.limit, count=paging.count)

        # Return library root
        items = [x.get_media_item() for x in self._library_items if x.parent_id is None]
        for item in items:
            item.title = self.get_localized(item.title)
        paging.count = len(items)
        item = self.get_root_item()
        item.title = self.get_localized(item.title)
        item.items = items
        return item, paging

    async def play_media(self, params: dict[str, Any]) -> StatusCodes:
        """Play given media id."""
        # pylint: disable=W1405
        media_id: str | None = params.get("media_id")
        media_type: str | None = params.get("media_type")
        # TODO handle action (enqueue, play...)
        # action = params.get("action")
        if media_id is None or media_type is None:
            return StatusCodes.BAD_REQUEST
        if media_type == MediaContent.MOVIE.value:
            if media_id.startswith("kodi://"):
                media_id = media_id.rstrip("/").rsplit("/", 1)[-1]
            _LOG.debug("[%s] Playing movie id %s", self._device.device_config.address, media_id)
            await self._device.server.Player.Open(**{"item": {"movieid": int(media_id)}})
        if media_type == MediaContent.EPISODE.value:
            if media_id.startswith("kodi://"):
                media_id = media_id.rstrip("/").rsplit("/", 1)[-1]
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
        elif media_type in ["kodi://videos/playlists", "kodi://music/playlists"]:
            _LOG.debug("[%s] Playing playlist %s", self._device.device_config.address, media_id)
            await self._device.server.Player.Open(**{"item": {"file": media_id}})
        elif media_id.startswith("kodi://playlist/"):
            media_data = media_id.split("/")
            playlist_id = int(media_data[-2])
            position = int(media_data[-1])
            _LOG.debug(
                "[%s] Playing playlist %s position %s", self._device.device_config.address, playlist_id, position
            )
            await self._device.server.Player.Open(**{"item": {"playlistid": playlist_id, "position": position}})

        return StatusCodes.OK

    def get_search_missing_categories(self, media_id: None | str, media_type: None | str) -> list[BrowseMediaItem]:
        """Return additional categories."""
        missing_modes: list[MediaContent] = [
            MediaContent.MOVIE,
            MediaContent.TV_SHOW,
            MediaContent.ALBUM,
            MediaContent.ARTIST,
            MediaContent.MUSIC,
        ]
        if media_type is not None:
            try:
                media_type = MediaContent(media_type)
                missing_modes.remove(media_type)
            except ValueError:
                pass
        return [
            BrowseMediaItem(
                title=self.get_localized(MEDIA_CONTENT_LABELS.get(x, "Videos")),
                media_id=media_id if media_id else "",
                media_type=x.value,
                media_class=x.value,
                can_search=True,
            )
            for x in missing_modes
        ]

    async def search_movies(
        self, query, media_id: str | None, media_type: str | None, paging: Pagination, max_results: int
    ) -> tuple[list[BrowseMediaItem], Pagination]:
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
            arguments["filter"] = {"field": "title", "operator": "contains", "value": query}
        _LOG.debug(
            "[%s] Searching video %s (media id %s, type %s) : %s",
            self._device.device_config.address,
            query,
            media_type,
            media_id,
            arguments,
        )
        medias = await self._device.server.VideoLibrary.GetMovies(**arguments)
        _LOG.debug("[%s] Searching video results %s", self._device.device_config.address, medias)
        new_paging = Pagination(page=paging.page, limit=paging.limit, count=paging.count)
        new_paging.count += medias.get("limits", {}).get("total", 0)
        for media in medias["movies"]:
            results.append(self.get_item_from_movie(media, "kodi://videos/all"))
        return results, new_paging

    async def search_tv_shows(
        self, query, media_id: str | None, media_type: str | None, paging: Pagination, max_results: int
    ) -> tuple[list[BrowseMediaItem], Pagination]:
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
            arguments["filter"] = {"field": "title", "operator": "contains", "value": query}
        _LOG.debug(
            "[%s] Searching TV Shows %s (%s) : %s",
            self._device.device_config.address,
            media_type,
            media_id,
            arguments,
        )
        medias = await self._device.server.VideoLibrary.GetTVShows(**arguments)
        new_paging = Pagination(page=paging.page, limit=paging.limit, count=paging.count)
        new_paging.count += medias.get("limits", {}).get("total", 0)
        for media in medias["tvshows"]:
            results.append(self.get_item_from_tvshow(media, "kodi://tvshows"))
        return results, new_paging

    async def search_albums(
        self, query, media_id: str | None, media_type: str | None, paging: Pagination, max_results: int
    ) -> tuple[list[BrowseMediaItem], Pagination]:
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
        new_paging = Pagination(page=paging.page, limit=paging.limit, count=paging.count)
        new_paging.count += medias.get("limits", {}).get("total", 0)
        for media in medias["albums"]:
            results.append(self.get_item_from_album(media, "kodi://music/albums"))
        return results, new_paging

    async def search_artists(
        self, query, media_id: str | None, media_type: str | None, paging: Pagination, max_results: int
    ) -> tuple[list[BrowseMediaItem], Pagination]:
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
            arguments["filter"] = {"field": "artist", "operator": "contains", "value": query}
        _LOG.debug(
            "[%s] Searching artists %s (%s) : %s",
            self._device.device_config.address,
            media_type,
            media_id,
            arguments,
        )
        medias = await self._device.server.AudioLibrary.GetArtists(**arguments)
        new_paging = Pagination(page=paging.page, limit=paging.limit, count=paging.count)
        new_paging.count += medias.get("limits", {}).get("total", 0)
        for media in medias["artists"]:
            results.append(self.get_item_from_artist(media, "kodi://music/artists"))
        return results, new_paging

    async def search_songs(
        self,
        query,
        media_id: str | None,
        media_type: str | None,
        paging: Pagination,
        media_search_filter: SearchMediaFilter | None,
        max_results: int,
    ) -> tuple[list[BrowseMediaItem], Pagination]:
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
                        {"field": "album", "operator": "contains", "value": media_search_filter.album},
                        {
                            "or": [
                                {"field": "title", "operator": "contains", "value": query},
                                {"field": "artist", "operator": "contains", "value": query},
                            ]
                        },
                    ]
                }
            elif media_search_filter.artist:
                arguments["filter"] = {
                    "and": [
                        {"field": "artist", "operator": "contains", "value": media_search_filter.artist},
                        {
                            "or": [
                                {"field": "title", "operator": "contains", "value": query},
                                {"field": "album", "operator": "contains", "value": query},
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
        new_paging = Pagination(page=paging.page, limit=paging.limit, count=paging.count)
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
        paging: Pagination | None,
    ) -> tuple[list[BrowseMediaItem], Pagination] | None:
        """Search media from given query and optional parameters."""
        # pylint: disable=R0915
        try:
            if paging is None:
                paging = Pagination(page=1, limit=10, count=0)
            else:
                paging = Pagination(page=paging.page, limit=paging.limit, count=0)
            max_results = 0
            do_pagination = True
            paging.count = 0
            results: list[BrowseMediaItem] = []
            # Add search categories if media_type is empty
            if not media_type and paging.page == 1:
                missing_categories = self.get_search_missing_categories(media_id, media_type)
                results.extend(missing_categories)
                paging.count += len(missing_categories)
                max_results = paging.limit - len(missing_categories)
                # Disable pagination because of multisearch
                do_pagination = False

            if (
                not media_type and self._device.device_config.search_media_default == KodiMediaSearchMode.VIDEOS
            ) or media_type == MediaContent.MOVIE.value:
                movies, local_paging = await self.search_movies(query, media_id, media_type, paging, max_results)
                paging.count += local_paging.count
                max_results -= len(movies)
                results.extend(movies)
            if (
                max_results > 0
                or (not media_type and self._device.device_config.search_media_default == KodiMediaSearchMode.TV_SHOWS)
                or media_type == MediaContent.TV_SHOW.value
            ):
                # if media_type is None and len(results) < paging.limit and paging.page == 1:
                #     end = limit - len(results)
                tv_shows, local_paging = await self.search_tv_shows(query, media_id, media_type, paging, max_results)
                paging.count += local_paging.count
                max_results -= len(tv_shows)
                results.extend(tv_shows)
            if (
                max_results > 0
                or not media_type
                and self._device.device_config.search_media_default == KodiMediaSearchMode.MUSIC
            ) or media_type == MediaContent.ALBUM.value:
                albums, local_paging = await self.search_albums(query, media_id, media_type, paging, max_results)
                paging.count += local_paging.count
                max_results -= len(albums)
                results.extend(albums)
            if max_results > 0 or media_type == MediaContent.ARTIST.value:
                artists, local_paging = await self.search_artists(query, media_id, media_type, paging, max_results)
                paging.count += local_paging.count
                max_results -= len(artists)
                results.extend(artists)
            if max_results > 0 or media_type == MediaContent.MUSIC.value:
                songs, local_paging = await self.search_songs(
                    query, media_id, media_type, paging, media_search_filter, max_results
                )
                paging.count += local_paging.count
                max_results -= len(songs)
                results.extend(songs)
            if not do_pagination and paging.count > paging.limit:
                paging.count = paging.limit

            _LOG.debug("[%s] Searching results %s %s", self._device.device_config.address, results, paging)
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
    media_type: MediaContent | str
    child_media_type: MediaContent
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
        return self.media_type.value if isinstance(self.media_type, MediaContent) else self.media_type

    @property
    def media_class_str(self) -> str | None:
        """Return media class in string format."""
        return self.media_class.value if self.media_class else None

    def get_media_item(self) -> BrowseMediaItem:
        """Build media item."""
        media_class = self.media_class.value if self.media_class else None
        return BrowseMediaItem(
            title=self.title,
            media_id=self.media_id,
            media_type=self.media_type_str,
            media_class=self.media_type_str if self.media_class is None else self.media_class_str,
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
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://videos",
        child_media_type=MediaContent.MOVIE,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id=None,
        title="TV Shows",
        media_type=MediaContent.TV_SHOW,
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://tvshows",
        child_media_type=MediaContent.TV_SHOW,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id=None,
        title="Music",
        media_type=MediaContent.MUSIC,
        media_class=MediaClass.DIRECTORY,
        media_id="kodi://music",
        child_media_type=MediaContent.MUSIC,
        output=KodiObjectType.EMPTY,
    ),
    KodiMediaEntry(
        parent_id=None,
        title="Sources",
        media_type=MediaContent.URL,
        media_class=MediaClass.DIRECTORY,
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
        arguments={"properties": MOVIE_PROPERTIES},
        child_media_type=MediaContent.MOVIE,
        output=KodiObjectType.MOVIE,
    ),
    KodiMediaEntry(
        parent_id="kodi://videos",
        title="Now playing",
        media_type=MediaContent.MOVIE,
        media_id="kodi://videos/current",
        command="VideoLibrary.GetMovies",
        arguments={
            "properties": MOVIE_PROPERTIES,
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
        arguments={"properties": MOVIE_PROPERTIES},
        child_media_type=MediaContent.MOVIE,
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
        child_media_type=MediaContent.MOVIE,
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
        child_media_type=MediaContent.PLAYLIST,
        output=KodiObjectType.PLAYLIST,
    ),
    KodiMediaEntry(
        parent_id="kodi://videos",
        title="Music videos",
        media_type=MediaContent.VIDEO,
        media_id="kodi://videos/music",
        command="VideoLibrary.GetMusicVideos",
        arguments={"properties": MOVIE_PROPERTIES},
        child_media_type=MediaContent.VIDEO,
        output=KodiObjectType.MOVIE,
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
        title="Now playing",
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
        media_class=MediaClass.EPISODE,
        command="VideoLibrary.GetRecentlyAddedEpisodes",
        arguments={"properties": EPISODE_PROPERTIES},
        child_media_type=MediaContent.EPISODE,
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
        child_media_type=MediaContent.GENRE,
        output=KodiObjectType.GENRE,
    ),
    KodiMediaEntry(
        parent_id="kodi://music",
        title="Albums",
        media_type=MediaContent.ALBUM,
        media_id="kodi://music/albums",
        command="AudioLibrary.GetAlbums",
        arguments={"properties": ["art", "artist", "albumduration"]},
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
        media_class=MediaClass.GENRE,
        media_id="kodi://music/genres",
        command="AudioLibrary.GetGenres",
        arguments={"properties": ["thumbnail"]},
        child_media_type=MediaContent.GENRE,
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
        child_media_type=MediaContent.PLAYLIST,
        output=KodiObjectType.PLAYLIST,
    ),
    KodiMediaEntry(
        parent_id="kodi://music",
        title="Songs",
        media_type=MediaContent.MUSIC,
        media_id="kodi://music/songs",
        command="AudioLibrary.GetSongs",
        arguments={"properties": ["art", "duration", "track", "album", "artist"]},
        child_media_type=MediaContent.MUSIC,
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
        child_media_type=MediaContent.MOVIE,
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
        child_media_type=MediaContent.MUSIC,
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
        child_media_type=MediaContent.IMAGE,
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
        child_media_type=MediaContent.URL,
        output=KodiObjectType.FILE,
    ),
]
