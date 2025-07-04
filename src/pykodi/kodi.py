"""
Implementation of a Kodi interface.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
import urllib

import aiohttp
import jsonrpc_async  # pylint: disable = E0401
import jsonrpc_base  # pylint: disable = E0401
import jsonrpc_websocket  # pylint: disable = E0401
from aiohttp import ServerTimeoutError

_LOG = logging.getLogger(__name__)


def get_kodi_connection(host, port, ws_port, username, password, ssl=False, timeout=5, session=None):
    """Return a Kodi connection."""
    if ws_port is None:
        return KodiHTTPConnection(host, port, username, password, ssl, timeout, session)
    return KodiWSConnection(host, port, ws_port, username, password, ssl, timeout, session)


class KodiConnection:
    """A connection to Kodi interface."""

    def __init__(self, host, port, username, password, ssl, timeout, session):
        """Initialize the object."""
        self._session = session
        self._created_session = False
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._created_session = True

        self._kwargs = {"timeout": timeout, "session": self._session}

        if username is not None:
            self._kwargs["auth"] = aiohttp.BasicAuth(username, password)
            image_auth_string = f"{username}:{password}@"
        else:
            image_auth_string = ""

        http_protocol = "https" if ssl else "http"

        self._image_url = f"{http_protocol}://{image_auth_string}{host}:{port}/image"

    async def connect(self):
        """Connect to kodi."""

    async def close(self):
        """Close the connection."""
        if self._created_session and self._session is not None:
            await self._session.close()
            self._session = None
            self._created_session = False

    @property
    def server(self):
        """Return server."""
        raise NotImplementedError

    @property
    def connected(self):
        """Is the server connected."""
        raise NotImplementedError

    @property
    def can_subscribe(self):
        """Can subscribe."""
        return False

    def thumbnail_url(self, thumbnail):
        """Get the URL for a thumbnail."""
        if thumbnail is None:
            return None

        url_components = urllib.parse.urlparse(thumbnail)
        if url_components.scheme == "image":
            return f"{self._image_url}/{urllib.parse.quote_plus(thumbnail)}"
        return None


class KodiHTTPConnection(KodiConnection):
    """An HTTP connection to Kodi."""

    def __init__(self, host, port, username, password, ssl, timeout, session):
        """Initialize the object."""
        super().__init__(host, port, username, password, ssl, timeout, session)

        http_protocol = "https" if ssl else "http"

        http_url = f"{http_protocol}://{host}:{port}/jsonrpc"

        self._http_server = jsonrpc_async.Server(http_url, **self._kwargs)

    @property
    def connected(self):
        """Is the server connected."""
        return True

    async def close(self):
        """Close the connection."""
        self._http_server = None
        await super().close()

    @property
    def server(self):
        """Active server for json-rpc requests."""
        return self._http_server


class KodiWSConnection(KodiConnection):
    """A WS connection to Kodi."""

    _connect_task = None

    def __init__(self, host, port, ws_port, username, password, ssl, timeout, session):
        """Initialize the object."""
        super().__init__(host, port, username, password, ssl, timeout, session)

        ws_protocol = "wss" if ssl else "ws"
        ws_url = f"{ws_protocol}://{host}:{ws_port}/jsonrpc"

        self._ws_server = jsonrpc_websocket.Server(ws_url, **self._kwargs)

    @property
    def connected(self):
        """Return whether websocket is connected."""
        return self._ws_server.connected

    @property
    def can_subscribe(self):
        """Can subscribe to vents."""
        return True

    async def connect(self):
        """Connect to kodi over websocket."""
        if self.connected:
            return
        try:
            if self._connect_task:
                try:
                    self._connect_task.cancel()
                    await self.close()
                except Exception:
                    pass
                self._connect_task = None

            self._connect_task = await self._ws_server.ws_connect()
        except (jsonrpc_base.jsonrpc.TransportError, asyncio.exceptions.CancelledError, ServerTimeoutError) as error:
            _LOG.error("Kodi connection error %s", error)
            raise CannotConnectError(error) from error

    async def close(self):
        """Close the connection."""
        await self._ws_server.close()
        await super().close()

    @property
    def server(self):
        """Active server for json-rpc requests."""
        return self._ws_server


class Kodi:
    """A high level Kodi interface."""

    def __init__(self, connection):
        """Initialize the object."""
        self._conn = connection
        self._server = connection.server

    async def ping(self):
        """Ping the server."""
        try:
            response = await self._server.JSONRPC.Ping()
            return response == "pong"
        except jsonrpc_base.jsonrpc.TransportError as error:
            if "401" in str(error):
                raise InvalidAuthError from error
            raise CannotConnectError from error

    async def get_application_properties(self, properties):
        """Get value of given properties."""
        return await self._server.Application.GetProperties(properties)

    async def get_player_properties(self, player, properties):
        """Get value of given properties."""
        return await self._server.Player.GetProperties(player["playerid"], properties)

    async def get_playing_item_properties(self, player, properties):
        """Get value of given properties."""
        return (await self._server.Player.GetItem(player["playerid"], properties))["item"]

    async def volume_up(self):
        """Send volume up command."""
        await self._server.Input.ExecuteAction("volumeup")

    async def volume_down(self):
        """Send volume down command."""
        await self._server.Input.ExecuteAction("volumedown")

    async def set_volume_level(self, volume):
        """Set volume level, range 0-100."""
        await self._server.Application.SetVolume(volume)

    async def mute(self, mute):
        """Send (un)mute command."""
        await self._server.Application.SetMute(mute)

    async def _set_play_state(self, state):
        players = await self.get_players()

        if players:
            await self._server.Player.PlayPause(players[0]["playerid"], state)

    async def play_pause(self):
        """Send toggle command command."""
        await self._set_play_state("toggle")

    async def play(self):
        """Send play command."""
        await self._set_play_state(True)

    async def pause(self):
        """Send pause command."""
        await self._set_play_state(False)

    async def stop(self):
        """Send stop command."""
        players = await self.get_players()

        if players:
            await self._server.Player.Stop(players[0]["playerid"])

    async def _goto(self, direction):
        players = await self.get_players()

        if players:
            if direction == "previous":
                # First seek to position 0. Kodi goes to the beginning of the
                # current track if the current track is not at the beginning.
                await self._server.Player.Seek(players[0]["playerid"], {"percentage": 0})

            await self._server.Player.GoTo(players[0]["playerid"], direction)

    async def next_track(self):
        """Send next track command."""
        await self._goto("next")

    async def previous_track(self):
        """Send previous track command."""
        await self._goto("previous")

    async def media_seek(self, position):
        """Send seek command."""
        players = await self.get_players()

        time = {"milliseconds": int((position % 1) * 1000)}

        position = int(position)

        time["seconds"] = int(position % 60)
        position /= 60

        time["minutes"] = int(position % 60)
        position /= 60

        time["hours"] = int(position)

        if players:
            await self._server.Player.Seek(players[0]["playerid"], {"time": time})

    async def play_item(self, item):
        """Play given item."""
        await self._server.Player.Open(**{"item": item})

    async def play_channel(self, channel_id):
        """Play the given channel."""
        await self.play_item({"channelid": channel_id})

    async def play_playlist(self, playlist_id):
        """Play the given playlist."""
        await self.play_item({"playlistid": playlist_id})

    async def play_directory(self, directory):
        """Play the given directory."""
        await self.play_item({"directory": directory})

    async def play_file(self, file):
        """Play the given file."""
        await self.play_item({"file": file})

    async def set_shuffle(self, shuffle):
        """Set shuffle mode, for the first player."""
        players = await self.get_players()
        if players:
            await self._server.Player.SetShuffle(**{"playerid": players[0]["playerid"], "shuffle": shuffle})

    async def call_method(self, method, **kwargs):
        """Run Kodi JSONRPC API method with params."""
        if "." not in method or len(method.split(".")) != 2:
            raise ValueError(f"Invalid method: {method}")
        return await getattr(self._server, method)(**kwargs)

    async def _add_item_to_playlist(self, item):
        await self._server.Playlist.Add(**{"playlistid": 0, "item": item})

    async def add_song_to_playlist(self, song_id):
        """Add song to default playlist (i.e. playlistid=0)."""
        await self._add_item_to_playlist({"songid": song_id})

    async def add_album_to_playlist(self, album_id):
        """Add album to default playlist (i.e. playlistid=0)."""
        await self._add_item_to_playlist({"albumid": album_id})

    async def add_artist_to_playlist(self, artist_id):
        """Add album to default playlist (i.e. playlistid=0)."""
        await self._add_item_to_playlist({"artistid": artist_id})

    async def clear_playlist(self):
        """Clear default playlist (i.e. playlistid=0)."""
        await self._server.Playlist.Clear(**{"playlistid": 0})

    async def get_artists(self, properties=None):
        """Get artists list."""
        return await self._server.AudioLibrary.GetArtists(**_build_query(properties=properties))

    async def get_artist_details(self, artist_id=None, properties=None):
        """Get artist details."""
        return await self._server.AudioLibrary.GetArtistDetails(
            **_build_query(artistid=artist_id, properties=properties)
        )

    async def get_albums(self, artist_id=None, album_id=None, properties=None):
        """Get albums list."""
        _filter = {}
        if artist_id:
            _filter["artistid"] = artist_id
        if album_id:
            _filter["albumid"] = album_id

        return await self._server.AudioLibrary.GetAlbums(**_build_query(filter=_filter, properties=properties))

    async def get_album_details(self, album_id, properties=None):
        """Get album details."""
        return await self._server.AudioLibrary.GetAlbumDetails(**_build_query(albumid=album_id, properties=properties))

    async def get_songs(self, artist_id=None, album_id=None, properties=None):
        """Get songs list."""
        _filter = {}
        if artist_id:
            _filter["artistid"] = artist_id
        if album_id:
            _filter["albumid"] = album_id

        return await self._server.AudioLibrary.GetSongs(**_build_query(filter=_filter, properties=properties))

    async def get_movies(self, properties=None):
        """Get movies list."""
        return await self._server.VideoLibrary.GetMovies(**_build_query(properties=properties))

    async def get_movie_details(self, movie_id, properties=None):
        """Get movie details."""
        return await self._server.VideoLibrary.GetMovieDetails(**_build_query(movieid=movie_id, properties=properties))

    async def get_seasons(self, tv_show_id, properties=None):
        """Get seasons list."""
        return await self._server.VideoLibrary.GetSeasons(**_build_query(tvshowid=tv_show_id, properties=properties))

    async def get_season_details(self, season_id, properties=None):
        """Get songs list."""
        return await self._server.VideoLibrary.GetSeasonDetails(
            **_build_query(seasonid=season_id, properties=properties)
        )

    async def get_episodes(self, tv_show_id, season_id, properties=None):
        """Get episodes list."""
        return await self._server.VideoLibrary.GetEpisodes(
            **_build_query(tvshowid=tv_show_id, season=season_id, properties=properties)
        )

    async def get_tv_shows(self, properties=None):
        """Get tv shows list."""
        return await self._server.VideoLibrary.GetTVShows(**_build_query(properties=properties))

    async def get_tv_show_details(self, tv_show_id=None, properties=None):
        """Get songs list."""
        return await self._server.VideoLibrary.GetTVShowDetails(
            **_build_query(tvshowid=tv_show_id, properties=properties)
        )

    async def get_channels(self, channel_group_id, properties=None):
        """Get channels list."""
        return await self._server.PVR.GetChannels(
            **_build_query(channelgroupid=channel_group_id, properties=properties)
        )

    async def get_players(self):
        """Return the active player objects."""
        return await self._server.Player.GetActivePlayers()

    async def send_notification(self, title, message, icon="info", displaytime=10000):
        """Display on-screen message."""
        await self._server.GUI.ShowNotification(title, message, icon, displaytime)

    def thumbnail_url(self, thumbnail):
        """Get the URL for a thumbnail."""
        return self._conn.thumbnail_url(thumbnail)


def _build_query(**kwargs):
    """Build query."""
    query = {}
    for key, val in kwargs.items():
        if val:
            query.update({key: val})

    return query


class CannotConnectError(Exception):
    """Exception to indicate an error in connection."""


class InvalidAuthError(Exception):
    """Exception to indicate an error in authentication."""
