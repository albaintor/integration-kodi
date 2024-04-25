"""
This module implements Kodi communication of the Remote Two integration driver.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""
import asyncio
import logging
from asyncio import AbstractEventLoop, Lock
from enum import IntEnum
from functools import wraps
from typing import Callable, Concatenate, Awaitable, Any, Coroutine, TypeVar, ParamSpec

import ucapi
from aiohttp import ClientSession, ServerTimeoutError
from pykodi.kodi import KodiWSConnection, InvalidAuthError

from config import KodiConfigDevice
from pyee import AsyncIOEventEmitter
from ucapi.media_player import Attributes as MediaAttr, States as MediaStates
from const import *
from jsonrpc_base.jsonrpc import ProtocolError, TransportError
from pykodi import CannotConnectError, Kodi
import urllib.parse

_KodiDeviceT = TypeVar("_KodiDeviceT", bound="KodiDevice")
_P = ParamSpec("_P")

_LOG = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 8.0
WEBSOCKET_WATCHDOG_INTERVAL = 10
CONNECTION_RETRIES = 10


class Events(IntEnum):
    """Internal driver events."""

    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2
    ERROR = 3
    UPDATE = 4
    # IP_ADDRESS_CHANGED = 6


class States(IntEnum):
    """State of a connected AVR."""

    UNKNOWN = 0
    UNAVAILABLE = 1
    OFF = 2
    ON = 3
    PLAYING = 4
    PAUSED = 5
    STOPPED = 6
    IDLE = 7


KODI_STATE_MAPPING = {
    States.OFF: MediaStates.OFF,
    States.ON: MediaStates.ON,
    States.STOPPED: MediaStates.STANDBY,
    States.PLAYING: MediaStates.PLAYING,
    States.PAUSED: MediaStates.PAUSED,
    States.IDLE: MediaStates.ON
}

def cmd_wrapper(
        func: Callable[Concatenate[_KodiDeviceT, _P], Awaitable[ucapi.StatusCodes | None]],
) -> Callable[Concatenate[_KodiDeviceT, _P], Coroutine[Any, Any, ucapi.StatusCodes | None]]:
    """Catch command exceptions."""

    @wraps(func)
    async def wrapper(obj: _KodiDeviceT, *args: _P.args, **kwargs: _P.kwargs) -> ucapi.StatusCodes:
        """Wrap all command methods."""
        try:
            await func(obj, *args, **kwargs)
            return ucapi.StatusCodes.OK
        except (TransportError, ProtocolError, ServerTimeoutError) as exc:
            # If Kodi is off, we expect calls to fail.
            if obj.state == States.OFF:
                log_function = _LOG.debug
            else:
                log_function = _LOG.error
            log_function(
                "Error calling %s on entity %s: %r trying to reconnect and send the command next",
                func.__name__,
                obj.id,
                exc,
            )
            # Kodi not connected, launch a connect task but
            # don't wait more than 5 seconds, then process the command if connected
            # else returns error
            connect_task = obj.event_loop.create_task(obj.connect())
            await asyncio.sleep(0)
            try:
                async with asyncio.timeout(5):
                    await connect_task
            except asyncio.TimeoutError:
                log_function(
                    "Timeout for reconnect, command won't be sent"
                )
                pass
            else:
                if not obj._connect_error:
                    try:
                        await func(obj, *args, **kwargs)
                        return ucapi.StatusCodes.OK
                    except (TransportError, ProtocolError, ServerTimeoutError) as exc:
                        log_function(
                            "Error calling %s on entity %s: %r trying to reconnect",
                            func.__name__,
                            obj.id,
                            exc,
                        )
            # If Kodi is off, we expect calls to fail.
            # await obj.event_loop.create_task(obj.connect())
            return ucapi.StatusCodes.BAD_REQUEST
        except Exception as ex:
            _LOG.error(
                "Unknown error %s",
                func.__name__)

    return wrapper


class KodiDevice:
    """Representing a LG TV Device."""

    def __init__(
            self,
            device_config: KodiConfigDevice,
            loop: AbstractEventLoop | None = None,
    ):
        """Create instance with given IP or hostname of AVR."""
        # TODO find a better ID than the IP address
        # identifier from configuration
        self._device_config = device_config  # For reconnection
        self.id: str = device_config.id
        # friendly name from configuration
        self._name: str = device_config.name
        self.event_loop = loop or asyncio.get_running_loop()
        self.events = AsyncIOEventEmitter(self.event_loop)
        self._session: ClientSession = None
        self._kodi_connection: KodiWSConnection = None
        self._kodi: Kodi = None
        self._supported_features = KODI_FEATURES
        self._players = None
        self._properties = {}
        self._item = {}
        self._app_properties = {}
        self._connect_error = False
        self._attr_available: bool = True
        self._volume = 0
        self._is_volume_muted = False
        self._media_position = 0
        self._media_duration = 0
        self._paused = False
        self._media_type = MediaType.VIDEO
        self._media_title = ""
        self._media_image_url = ""
        self._media_artist = ""
        self._media_album = ""
        self._thumbnail = None
        self._attr_state = States.OFF
        self._connect_task = None
        self._buffered_callbacks = {}
        self._connect_lock = Lock()
        self._reconnect_retry = 0
        self._kodi_ws_task = None
        _LOG.debug("Kodi instance created: %s", device_config.address)
        self.event_loop.create_task(self.init_connection())

    async def init_connection(self):
        if self._kodi_connection:
            try:
                await self._kodi_connection.close()
            except Exception:
                pass
            finally:
                self._kodi_connection = None
        if self._session:# and not self._session.closed:
            try:
                await self._session.close()
            except Exception as ex:
                _LOG.warning("Error closing session to %s : %s", self._device_config.address, ex)
            self._session = None
        self._session = ClientSession(raise_for_status=True,
            # timeout=ClientTimeout(
            # sock_connect=DEFAULT_TIMEOUT,
            # # Maximal number of seconds for connecting to a peer for a new connection, not given from a pool. See also connect.
            # sock_read=DEFAULT_TIMEOUT)
            # Maximal number of seconds for reading a portion of data from a peer=DEFAULT_TIMEOUT
        )
        self._session.loop.set_exception_handler(self.exception_handler)
        self._kodi_connection: KodiWSConnection = KodiWSConnection(
            host=self._device_config.address,
            port=self._device_config.port,
            ws_port=self._device_config.ws_port,
            username=self._device_config.username,
            password=self._device_config.password,
            ssl=self._device_config.ssl,
            timeout=DEFAULT_TIMEOUT,
            session=self._session
        )
        self._kodi = Kodi(self._kodi_connection)

    def get_state(self) -> States:
        if self._kodi_is_off:
            return States.OFF
        if self._no_active_players:
            return States.IDLE
        if self._properties["speed"] == 0 or self._paused:
            return States.PAUSED
        return States.PLAYING

    def on_speed_event(self, sender, data):
        """Handle player changes between playing and paused."""
        _LOG.debug("Kodi playback changed %s", data)
        self._properties["speed"] = data["player"]["speed"]
        self.event_loop.create_task(self._update_states())

    def on_stop(self, sender, data):
        """Handle the stop of the player playback."""
        # Prevent stop notifications which are sent after quit notification
        _LOG.debug("Kodi stopped")
        if self._kodi_is_off:
            return
        current_state = self._attr_state
        self._reset_state([])
        if current_state != self.get_state():
            self._attr_state = self.get_state()
            self.events.emit(Events.UPDATE, self.id, {MediaAttr.STATE: KODI_STATE_MAPPING[self.state]})

    def on_volume_changed(self, sender, data):
        """Handle the volume changes."""
        _LOG.debug("Kodi volume changed %s", data)
        volume = self._volume
        muted = self._is_volume_muted
        self._app_properties["volume"] = data["volume"]
        self._app_properties["muted"] = data["muted"]
        updated_data = {}
        if volume != self._volume:
            self._volume = int(self._app_properties["volume"])
            updated_data[MediaAttr.VOLUME] = self._volume
        if muted != self._app_properties["muted"]:
            self._is_volume_muted = self._app_properties["muted"]
            updated_data[MediaAttr.MUTED] = self._is_volume_muted
        if updated_data:
            self.events.emit(Events.UPDATE, self.id, updated_data)

    def on_key_press(self, sender, data):
        """Handle a incoming key press notification."""
        _LOG.debug("Keypress %s %s", sender, data)

    async def on_quit(self, sender, data):
        """Reset the player state on quit action."""
        await self._clear_connection()

    def _register_ws_callbacks(self):
        _LOG.debug("Kodi register callbacks")
        self._kodi_connection.server.Player.OnPause = self.on_speed_event
        self._kodi_connection.server.Player.OnPlay = self.on_speed_event
        self._kodi_connection.server.Player.OnAVStart = self.on_speed_event
        self._kodi_connection.server.Player.OnAVChange = self.on_speed_event
        self._kodi_connection.server.Player.OnResume = self.on_speed_event
        self._kodi_connection.server.Player.OnSpeedChanged = self.on_speed_event
        self._kodi_connection.server.Player.OnSeek = self.on_speed_event
        self._kodi_connection.server.Player.OnStop = self.on_stop
        self._kodi_connection.server.Application.OnVolumeChanged = (
            self.on_volume_changed
        )
        # self._kodi_connection.server.Other.OnKeyPress = self.on_key_press
        self._kodi_connection.server.System.OnQuit = self.on_quit
        self._kodi_connection.server.System.OnRestart = self.on_quit
        self._kodi_connection.server.System.OnSleep = self.on_quit

    async def _on_ws_connected(self):
        """Call after ws is connected."""
        self._connect_error = False
        self._register_ws_callbacks()
        version = (await self._kodi.get_application_properties(["version"]))["version"]
        sw_version = f"{version['major']}.{version['minor']}"

    async def _clear_connection(self, close=True):
        self._reset_state()
        # TODO update state : self.async_write_ha_state()
        if close:
            await self._kodi_connection.close()

    async def _ping(self):
        try:
            await self._kodi.ping()
        except (TransportError, CannotConnectError, ServerTimeoutError):
            if not self._connect_error:
                self._connect_error = True
                _LOG.warning("Unable to ping Kodi via websocket")
            await self._clear_connection()
        except Exception as ex:
            _LOG.error("Unknown exception ping", ex)
        else:
            self._connect_error = False

    async def _async_connect_websocket_if_disconnected(self, *_) -> bool:
        """Reconnect the websocket if it fails."""
        if not self._kodi_connection.connected and self._reconnect_retry >= CONNECTION_RETRIES:
            return False
        if not self._kodi_connection.connected:
            self._reconnect_retry += 1
            _LOG.debug("Kodi websocket %s not connected, retry %s / %s", self._device_config.address,
                       self._reconnect_retry, CONNECTION_RETRIES)
            try:
                await asyncio.wait_for(self.connect(), DEFAULT_TIMEOUT*2)
            except asyncio.TimeoutError:
                _LOG.debug("Kodi websocket too slow to reconnect on %s", self._device_config.address)
        else:
            await self._ping()
        return True
            # _LOG.debug("Kodi websocket %s ping : %s", self._device_config.address, self._connect_error)

    def exception_handler(self, loop, context):
        if not context or context.get('exception', None) is None:
            return
        exception = context.get('exception', None)
        message = context.get('message', None)
        if message is None:
            message = ""
        # log exception
        _LOG.error(f'Websocket task failed to %s, msg={message}, exception={exception}', self._device_config.address)

    async def start_watchdog(self):
        """Start websocket watchdog."""
        while True:
            await asyncio.sleep(WEBSOCKET_WATCHDOG_INTERVAL)
            if not await self._async_connect_websocket_if_disconnected():
                _LOG.debug("Stop watchdog for %s", self._device_config.address)
                self._connect_task = None
                break

    async def connect(self) -> bool:
        """Connect to Kodi via websocket protocol."""
        try:
            if self._connect_lock.locked():
                _LOG.debug("Connect to %s : already in progress, returns", self._device_config.address)
                return True
            _LOG.debug("Connecting to %s", self._device_config.address)
            await self._connect_lock.acquire()
            if self._kodi_connection and self._kodi_connection.connected:
                _LOG.debug("Already connected to %s", self._device_config.address)
                return True
            await self.init_connection()

            # This method was buggy, this is the reason why pykodi library has been integrated into the driver
            # TODO report the fix
            await self._kodi_connection.connect()
            await self._on_ws_connected()
            await self._ping()
            await self._update_states()
            self._connect_error = False
            _LOG.debug("Connection successful to %s", self._device_config.address)
            self._reconnect_retry = 0
            if self._connect_task is None:
                self._connect_task = self.event_loop.create_task(self.start_watchdog())
            return True
        except (TransportError, CannotConnectError, ServerTimeoutError) as ex:
            if not self._connect_error:
                self._connect_error = True
                _LOG.warning("Unable to connect to Kodi via websocket to %s", self._device_config.address)
                # , ex, stack_info=True, exc_info=True)
            await self._clear_connection(False)
        except Exception as ex:
            _LOG.error("Unknown exception connect to %s : %s", self._device_config.address, ex)
        finally:
            # After 10 retries, reconnection delay will go from 10 to 30s and stop logging
            if self._reconnect_retry >= CONNECTION_RETRIES and self._connect_error:
                _LOG.debug("Kodi websocket not connected, abort retries to %s", self._device_config.address)
                if self._connect_task:
                    self._connect_task.cancel()
                    self._connect_task = None
            elif self._connect_task is None:
                self._connect_task = self.event_loop.create_task(self.start_watchdog())
            self._attr_available = True
            self.events.emit(Events.CONNECTED, self.id)
            self._connect_lock.release()

    async def disconnect(self):
        """Disconnect from TV."""
        _LOG.debug("Disconnect %s", self.id)
        try:
            if self._connect_task:
                self._connect_task.cancel()
            await self._kodi_connection.close()
            self._attr_state = States.OFF
        except CannotConnectError:
            pass
        except InvalidAuthError as error:
            _LOG.error(
                "Logout to %s failed: [%s]", self._device_config.address,
                error,
            )
            self._attr_available = False
        finally:
            self._connect_task = None

    def _reset_state(self, players=None):
        self._players = players
        self._properties = {}
        self._item = {}
        self._app_properties = {}
        self._media_position_updated_at = None
        self._media_position = None

    async def _update_states(self) -> None:
        """Update entity state attributes."""
        if not self._kodi_connection.connected:
            self._reset_state()
            return
        updated_data = {}

        self._players = await self._kodi.get_players()
        if self._kodi_is_off:
            current_state = self.state
            self._reset_state()
            if current_state != self.state:
                self.events.emit(Events.UPDATE, self.id, {MediaAttr.STATE: KODI_STATE_MAPPING[self.state]})
            return

        if self._players and len(self._players) > 0:
            self._app_properties = await self._kodi.get_application_properties(
                ["volume", "muted"]
            )
            volume = int(self._app_properties["volume"])
            if self._volume != volume:
                self._volume = volume
                updated_data[MediaAttr.VOLUME] = self._volume
            muted = self._app_properties["muted"]
            if muted != self._is_volume_muted:
                self._is_volume_muted = muted
                updated_data[MediaAttr.MUTED] = muted

            self._properties = await self._kodi.get_player_properties(
                self._players[0], ["time", "totaltime", "speed", "live"]
            )
            position = self._properties["time"]
            if position:
                media_position = position["hours"] * 3600 + position["minutes"] * 60 + position["seconds"]
            else:
                media_position = 0
            if self._media_position != media_position:
                self._media_position = media_position
                updated_data[MediaAttr.MEDIA_POSITION] = media_position

            totaltime = self._properties["totaltime"]
            if totaltime:
                duration = totaltime["hours"] * 3600 + totaltime["minutes"] * 60 + totaltime["seconds"]
            else:
                duration = 0
            if self._media_duration != duration:
                self._media_duration = duration
                updated_data[MediaAttr.MEDIA_POSITION] = self.media_position
                updated_data[MediaAttr.MEDIA_DURATION] = duration

            self._item = await self._kodi.get_playing_item_properties(
                self._players[0],
                [
                    "title",
                    "file",
                    "uniqueid",
                    "thumbnail",
                    "artist",
                    "albumartist",
                    "showtitle",
                    "album",
                    "season",
                    "episode",
                ]
            )
            thumbnail = self._item.get("thumbnail")
            if thumbnail != self._thumbnail:
                self._thumbnail = thumbnail
                self._media_image_url = self._kodi.thumbnail_url(thumbnail)
                # Not working with smb links.
                # TODO extend this approach for other media types
                if self._item['type'] == "movie" and "@smb" in thumbnail:
                    try:
                        result = await self._kodi.call_method("VideoLibrary.GetAvailableArt",
                                                              **{"item": {"movieid": self._item['id']},
                                                                 "arttype": "poster"})
                        if result and len(result['availableart']) > 0:
                            self._media_image_url = result['availableart'][0]['url']
                            self._media_image_url = self._media_image_url.removeprefix("image://").removesuffix("/")
                            self._media_image_url = urllib.parse.unquote(self._media_image_url)
                    except Exception:
                        pass

                _LOG.debug("Kodi changed thumbnail %s => %s", thumbnail, self._media_image_url)
                # self._media_image_url = self._media_image_url.removesuffix('%2F')
                updated_data[MediaAttr.MEDIA_IMAGE_URL] = self._media_image_url

            media_title = self._item.get("title") or self._item.get("label") or self._item.get("file")
            if media_title != self._media_title:
                self._media_title = media_title
                updated_data[MediaAttr.MEDIA_TITLE] = self._media_title
            artists = self._item.get("artist")
            if artists and len(artists) > 0:
                media_artist = artists[0]
            else:
                media_artist = ""
            if media_artist != self._media_artist:
                self._media_artist = media_artist
                updated_data[MediaAttr.MEDIA_ARTIST] = self._media_artist
            media_album = self._item.get("album")
            if media_album != self._media_album:
                self._media_album = media_album
                updated_data[MediaAttr.MEDIA_ALBUM] = self._media_album
            item_type = KODI_MEDIA_TYPES.get(self._item.get("type"))
            if item_type != self._media_type:
                self._media_type = item_type
                updated_data[MediaAttr.MEDIA_TYPE] = self._media_type
        else:
            self._reset_state([])
            self._media_position = 0
            self._media_duration = 0
            self._media_title = ""
            self._media_album = ""
            self._media_artist = ""
            self._media_image_url = ""
            updated_data[MediaAttr.MEDIA_POSITION] = 0
            updated_data[MediaAttr.MEDIA_DURATION] = 0
            updated_data[MediaAttr.MEDIA_TITLE] = ""
            updated_data[MediaAttr.MEDIA_ALBUM] = ""
            updated_data[MediaAttr.MEDIA_ARTIST] = ""
            updated_data[MediaAttr.MEDIA_IMAGE_URL] = ""

        if self._attr_state != self.get_state():
            self._attr_state = self.get_state()
            updated_data[MediaAttr.STATE] = KODI_STATE_MAPPING[self.get_state()]

        if updated_data:
            self.events.emit(Events.UPDATE, self.id, updated_data)

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self._attr_available

    @available.setter
    def available(self, value: bool):
        """Set device availability and emit CONNECTED / DISCONNECTED event on change."""
        if self._attr_available != value:
            self._attr_available = value
            # self.events.emit(Events.CONNECTED if value else Events.DISCONNECTED, self.id)

    @property
    def host(self) -> str:
        """Return the host of the device as string."""
        return self._device_config.address

    @property
    def _kodi_is_off(self):
        return self._players is None

    @property
    def _no_active_players(self):
        return not self._players

    @property
    def state(self) -> States:
        """Return the cached state of the device."""
        return self._attr_state

    @property
    def supported_features(self) -> list[Features]:
        return self._supported_features

    @property
    def media_position(self):
        return self._media_position

    @property
    def media_duration(self):
        return self._media_duration

    # @property
    # def source_list(self) -> list[str]:
    #     """Return a list of available input sources."""
    #     return sorted(self._sources)
    #
    # @property
    # def source(self) -> str:
    #     """Return the current input source."""
    #     return self._active_source

    @property
    def is_volume_muted(self) -> bool:
        """Return boolean if volume is currently muted."""
        return self._is_volume_muted

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..100)."""
        return self._volume

    @property
    def media_image_url(self) -> str:
        """Image url of current playing media."""
        return self._media_image_url

    @property
    def media_title(self) -> str:
        """Title of current playing media."""
        return self._media_title

    @property
    def media_album(self) -> str:
        """Title of current playing media."""
        return self._media_album

    @property
    def media_artist(self) -> str:
        """Title of current playing media."""
        return self._media_artist

    @property
    def media_type(self) -> MediaType:
        return self._media_type

    @cmd_wrapper
    async def set_volume_level(self, volume: float | None):
        """Set volume level, range 0..100."""
        if volume is None:
            return ucapi.StatusCodes.BAD_REQUEST
        _LOG.debug("Kodi setting volume to %s", volume)
        await self._kodi.set_volume_level(int(volume))

    @cmd_wrapper
    async def volume_up(self):
        """Send volume-up command to Kodi"""
        await self._kodi.volume_up()

    @cmd_wrapper
    async def volume_down(self):
        """Send volume-down command to Kodi"""
        await self._kodi.volume_down()

    @cmd_wrapper
    async def mute(self, muted: bool):
        """Send mute command to Kodi"""
        _LOG.debug("Sending mute: %s", muted)
        await self._kodi.mute(muted)

    @cmd_wrapper
    async def async_media_play(self):
        """Send play command."""
        self._paused = False
        await self._kodi.play()

    @cmd_wrapper
    async def async_media_pause(self):
        """Send media pause command to media player."""
        self._paused = True
        await self._kodi.pause()

    @cmd_wrapper
    async def play_pause(self):
        """Send toggle-play-pause command to Kodi"""
        if self._paused:
            await self.async_media_play()
        else:
            await self.async_media_pause()

    @cmd_wrapper
    async def stop(self):
        """Send stop command to Kodi"""
        await self._kodi.stop()

    @cmd_wrapper
    async def next(self):
        """Send next-track command to Kodi"""
        await self._kodi.next_track()

    @cmd_wrapper
    async def previous(self):
        """Send previous-track command to Kodi"""
        await self._kodi.previous_track()

    @cmd_wrapper
    async def media_seek(self, position: float):
        """Send seek command."""
        await self._kodi.media_seek(position)

    @cmd_wrapper
    async def context_menu(self):
        """Send display context menu command."""
        if await self.is_fullscreen_video():
            await self._kodi.call_method("Input.ShowOSD")
        else:
            await self._kodi.call_method("Input.ContextMenu")

    @cmd_wrapper
    async def home(self):
        """Send Home command."""
        await self._kodi.call_method("Input.Home")

    @cmd_wrapper
    async def power_off(self):
        """Send Power Off command."""
        try:
            await self._kodi.call_method("Application.Quit")
        except TransportError as ex:
            _LOG.info("Power off : client is already disconnected %s", ex)
            try:
                await self.event_loop.create_task(self._update_states())
            except Exception:
                pass

    @cmd_wrapper
    async def command_button(self, button: BUTTON_KEYMAP):
        """Call a button command."""
        await self._kodi.call_method("Input.ButtonEvent",
                                     **{"button": button["button"],
                                        "keymap": button.get("keymap", "KB"),
                                        "holdtime": button.get("holdtime", 0)})

    @cmd_wrapper
    async def command_action(self, command: str):
        """Send custom command see https://kodi.wiki/view/Keymap."""
        await self._kodi.call_method("Input.ExecuteAction",
                                     **{"action": command})

    @cmd_wrapper
    async def seek(self, media_position: int):
        """Seek to given position in seconds."""
        if self._no_active_players or media_position is None:
            return
        player_id = self._players[0]["playerid"]
        m, s = divmod(media_position, 60)
        h, m = divmod(m, 60)
        await self._kodi.call_method("Player.Seek",
             **{"playerid": player_id,
                "value": {"time": {"hours": h, "minutes": m, "seconds": s, "milliseconds": 0}}})

    async def is_fullscreen_video(self) -> bool:
        """Check if Kodi is in fullscreen (playing video)"""
        if self.state in (States.OFF, States.IDLE, States.UNKNOWN):
            return False
        try:
            result = await self._kodi.call_method("Gui.GetProperties",
                                                  **{"properties": ["fullscreen"]})
            if result["fullscreen"] and result["fullscreen"] == True:
                return True
        except Exception as ex:
            _LOG.debug("Couldn't retrieve Kodi's window state %s", ex)
        return False

    # TODO seek
