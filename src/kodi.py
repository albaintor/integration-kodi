"""
This module implements Kodi communication of the Remote Two integration driver.

:copyright: (c) 2026 by Albaintor
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import base64
import datetime
import logging
import time
import urllib.parse
from asyncio import AbstractEventLoop, Future, Lock, Task, shield
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Concatenate,
    Coroutine,
    Literal,
    ParamSpec,
    TypeVar,
)

import jsonrpc_base
import ucapi
from aiohttp import ClientOSError, ClientSession, ServerTimeoutError
from jsonrpc_base.jsonrpc import (  # pylint: disable = E0401
    ProtocolError,
    TransportError,
)
from pyee.asyncio import AsyncIOEventEmitter
from ucapi.media_player import Attributes as MediaAttr
from ucapi.media_player import Features, MediaType
from ucapi.media_player import States as MediaStates
from ucapi.select import Attributes as SelectAttributes
from ucapi.select import States as SelectStates

from config import KodiConfigDevice
from const import (
    KODI_FEATURES,
    KODI_MEDIA_TYPES,
    ButtonKeymap,
    KodiSelects,
    KodiSensors,
    KodiStreamConfig,
)
from languages import LANGUAGES, LANGUAGES_KEYS
from pykodi.kodi import CannotConnectError, InvalidAuthError, Kodi, KodiWSConnection

# pylint: disable=C0302
_KodiDeviceT = TypeVar("_KodiDeviceT", bound="KodiDevice")
_P = ParamSpec("_P")
_R = TypeVar("_R", bound=ucapi.StatusCodes)

_LOG = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 8.0
ARTWORK_TIMEOUT = 5.0
WEBSOCKET_WATCHDOG_INTERVAL = 10
CONNECTION_RETRIES = 30
UPDATE_POSITION_INTERVAL = 300
UPDATE_STATE_RETRY = 2
UPDATE_LOCK_TIMEOUT = 10.0
ERROR_OS_WAIT = 0.5


class Events(StrEnum):
    """Internal driver events."""

    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"
    UPDATE = "UPDATE"
    # IP_ADDRESS_CHANGED = 6


class ArtworkType(IntEnum):
    """Artwork types."""

    THUMBNAIL = 0
    FANART = 1
    POSTER = 2
    LANDSCAPE = 3
    KEYART = 4
    BANNER = 5
    CLEARART = 6
    CLEARLOGO = 7
    DISCART = 8
    ICON = 9


def _get_language_name(lang: str, app_language="en_US") -> str:
    """Retrieve language name from language code."""
    if lang == "":
        return lang
    app_language_code = LANGUAGES_KEYS.get(app_language, None)
    if app_language_code is None:
        app_language_code = "en"
    stream_language = LANGUAGES.get(lang, None)
    if stream_language is None:
        return lang
    return stream_language.get(app_language_code, stream_language.get("en", lang))


@dataclass
class Track:
    """Track name and index."""

    index: int
    language_name: str
    stream_name: str
    enabled: bool = True
    forced: bool | None = None
    impaired: bool | None = None
    default: bool | None = None

    @property
    def get_full_name(self) -> str:
        """Return full track name."""
        if self.language_name != self.stream_name:
            return f"{self.language_name.title()} {self.stream_name}" if self.language_name else self.stream_name
        return self.language_name.title()

    @property
    def get_stream_name(self) -> str:
        """Return stream name."""
        return self.stream_name if self.stream_name else self.language_name

    @property
    def get_language_name(self) -> str:
        """Return language name."""
        return self.language_name.title() if self.language_name else self.stream_name

    def get_track_name(self, config: KodiStreamConfig) -> str:
        """Return computed track name."""
        attributes = ""
        if self.forced:
            attributes += " (forced)"
        if self.impaired:
            attributes += " (impaired)"
        if config == KodiStreamConfig.FULL:
            return self.get_full_name + attributes
        if config == KodiStreamConfig.STREAM_NAME:
            return self.get_stream_name + attributes
        return self.get_language_name + attributes

    @staticmethod
    def get_disabled_track(app_language: str | None) -> "Track":
        """Return disabled track information."""
        language = _get_language_name("dis", app_language)
        return Track(index=-1, language_name=language, stream_name="", enabled=False)


def debounce(wait):
    """Debounce function."""

    def decorator(func):
        task: Task | None = None

        @wraps(func)
        async def debounced(*args, **kwargs):
            nonlocal task

            async def call_func():
                """Call wrapped function."""
                await asyncio.sleep(wait)
                await func(*args, **kwargs)

            if task and not task.done():
                task.cancel()
            task = asyncio.create_task(call_func())
            return task

        return debounced

    return decorator


async def retry_call_command(
    timeout: float,
    bufferize: bool,
    func: Callable[Concatenate[_KodiDeviceT, _P], Awaitable[_R]],
    obj: _KodiDeviceT,
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> ucapi.StatusCodes:
    """Retry call command when failed."""
    # pylint: disable=W0212
    # Launch reconnection task if not active
    obj._reconnect_retry = 0
    if not obj._connection_status:
        obj._connection_status = obj.event_loop.create_future()
    if not obj._connect_lock.locked():
        obj.event_loop.create_task(obj.connect())
        await asyncio.sleep(0)

    # If the command should be bufferized (and retried later) add it to the list and returns OK
    if bufferize:
        _LOG.debug("[%s] Bufferize command %s %s", obj.device_config.address, func, args)
        obj._buffered_callbacks[time.time()] = {"object": obj, "function": func, "args": args, "kwargs": kwargs}
        return ucapi.StatusCodes.OK
    try:
        # Else (no bufferize) wait (not more than "timeout" seconds) for the connection to complete
        async with asyncio.timeout(max(timeout - 1, 1)):
            await shield(obj._connection_status)
    except asyncio.TimeoutError:
        # (Re)connection failed at least at given time
        if obj.state == MediaStates.OFF:
            log_function = _LOG.debug
        else:
            log_function = _LOG.error
        log_function("[%s] Timeout for reconnect, command will probably fail", obj.device_config.address)
    # Try to send the command anyway
    await func(obj, *args, **kwargs)
    return ucapi.StatusCodes.OK


def retry(*, timeout: float = 5, bufferize=False) -> Callable[
    [Callable[Concatenate[_KodiDeviceT, _P], Awaitable[_R]]],
    Callable[Concatenate[_KodiDeviceT, _P], Awaitable[_R]],
]:
    """Retry call to given command."""

    def decorator(
        func: Callable[Concatenate[_KodiDeviceT, _P], Awaitable[ucapi.StatusCodes | None]],
    ) -> Callable[Concatenate[_KodiDeviceT, _P], Coroutine[Any, Any, ucapi.StatusCodes | None]]:
        @wraps(func)
        async def wrapper(obj: _KodiDeviceT, *args: _P.args, **kwargs: _P.kwargs) -> ucapi.StatusCodes:
            """Wrap all command methods."""
            # pylint: disable = W0212, W0718
            try:
                if obj._kodi_connection and obj._kodi_connection.connected:
                    await func(obj, *args, **kwargs)
                    return ucapi.StatusCodes.OK
                return await retry_call_command(timeout, bufferize, func, obj, *args, **kwargs)
            except (TransportError, ProtocolError, ServerTimeoutError) as ex:
                if obj.state == MediaStates.OFF:
                    log_function = _LOG.debug
                else:
                    log_function = _LOG.error
                log_function(
                    "[%s] Error calling %s on (%s): %r trying to reconnect",
                    obj.device_config.address,
                    func.__name__,
                    obj._name,
                    ex,
                )
                try:
                    return await retry_call_command(timeout, bufferize, func, obj, *args, **kwargs)
                except (TransportError, ProtocolError, ServerTimeoutError) as ex2:
                    log_function(
                        "[%s] Error calling %s on (%s): %r",
                        obj.device_config.address,
                        func.__name__,
                        obj._name,
                        ex2,
                    )
                    return ucapi.StatusCodes.BAD_REQUEST
            # pylint: disable = W0718
            except Exception as ex:
                _LOG.error("[%s] Unknown error %s %s", obj.device_config.address, func.__name__, ex)
                return ucapi.StatusCodes.BAD_REQUEST

        return wrapper

    return decorator


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
        self._device_config: KodiConfigDevice = device_config  # For reconnection
        self.id: str = device_config.id
        # friendly name from configuration
        self._name: str = device_config.name
        self.event_loop = loop or asyncio.get_running_loop()
        self.events = AsyncIOEventEmitter(self.event_loop)
        self._session: ClientSession | None = None
        self._kodi_connection: KodiWSConnection | None = None
        self._kodi: Kodi | None = None
        self._supported_features = KODI_FEATURES
        self._players = None
        self._properties = {}
        self._item = {}
        self._app_properties = {}
        self._connect_error = False
        self._available: bool = True
        self._volume = 0
        self._is_volume_muted = False
        self._media_position = 0
        self._media_duration = 0
        self._media_position_updated_at: datetime.datetime | None = None
        self._media_type = MediaType.VIDEO
        self._media_title = ""
        self._media_image_url = ""
        self._media_image_data = ""
        self._media_artist = ""
        self._media_album = ""
        self._thumbnail: str | None = None
        self._attr_state = MediaStates.OFF
        self._websocket_task = None
        self._buffered_callbacks = {}
        self._connect_lock = Lock()
        self._reconnect_retry = 0
        self._kodi_ws_task = None
        _LOG.debug("[%s] Kodi instance created", device_config.address)
        # self.event_loop.create_task(self.init_connection())
        self._connection_status: Future | None = None
        self._buffered_callbacks = {}
        self._update_lock = Lock()
        self._update_lock_time: float = 0
        self._position_timestamp: float | None = None
        self._update_position_task = None
        self._update_state_retry = 0
        self._temporary_title: str | None = None
        self._chapters: list[dict[str, Any]] | None = None
        self._source: str | None = None
        self._audio_stream: str = ""
        self._subtitle_stream = ""
        self._app_language: str | None = None

    async def init_connection(self):
        """Initialize connection to device."""
        # pylint: disable = W0718
        if self._kodi_connection:
            try:
                await self._kodi_connection.close()
            except Exception:
                pass
            finally:
                self._kodi_connection = None
        if self._session:  # and not self._session.closed:
            try:
                await self._session.close()
            except Exception as ex:
                _LOG.warning("[%s] Error closing session : %s", self._device_config.address, ex)
            self._session = None
        # timeout=ClientTimeout(
        # sock_connect=DEFAULT_TIMEOUT,
        # Maximal number of seconds for connecting to a peer for a new connection,
        # not given from a pool. See also connect.
        # sock_read=DEFAULT_TIMEOUT)
        # Maximal number of seconds for reading a portion of data from a peer=DEFAULT_TIMEOUT
        self._session = ClientSession(raise_for_status=True)
        self.event_loop.set_exception_handler(self.exception_handler)
        # self.event_loop.set_exception_handler(self.exception_handler)
        # self._session.loop.set_exception_handler(self.exception_handler)
        self._kodi_connection: KodiWSConnection = KodiWSConnection(
            host=self._device_config.address,
            port=self._device_config.port,
            ws_port=self._device_config.ws_port,
            username=self._device_config.username,
            password=self._device_config.password,
            ssl=self._device_config.ssl,
            timeout=DEFAULT_TIMEOUT,
            session=self._session,
        )
        self._kodi = Kodi(self._kodi_connection)

    def get_state(self) -> MediaStates:
        """Get state of device."""
        if self._kodi_is_off:
            return MediaStates.OFF
        if self._no_active_players:
            return MediaStates.ON
        if self._properties and self._properties["speed"] == 0:
            return MediaStates.PAUSED
        return MediaStates.PLAYING

    # pylint: disable = W0613
    def on_speed_event(self, sender: str, data: dict[str, Any]):
        """Handle player changes between playing and paused."""
        _LOG.debug("[%s] Kodi playback changed %s", self.device_config.address, data)
        if "speed" in data.get("player", {}):
            self._properties["speed"] = data["player"]["speed"]
        self.event_loop.create_task(self._update_states())

    # pylint: disable = W0613
    def on_stop(self, sender: str, data: dict[str, Any]):
        """Handle the stop of the player playback."""
        # Prevent stop notifications which are sent after quit notification
        _LOG.debug("[%s] Kodi stopped", self.device_config.address)
        if self._kodi_is_off:
            return
        current_state = self._attr_state
        self._reset_state([])
        if current_state != self.get_state():
            self._attr_state = self.get_state()
            self.events.emit(Events.UPDATE, self.id, {MediaAttr.STATE: self.state})

    # pylint: disable = W0613
    def on_volume_changed(self, sender: Any, data: dict[str, Any]):
        """Handle the volume changes."""
        _LOG.debug("[%s] Kodi volume changed %s", self.device_config.address, data)
        volume = self._volume
        muted = self._is_volume_muted
        self._app_properties["volume"] = data["volume"]
        self._app_properties["muted"] = data["muted"]
        updated_data = {}
        if volume != self._volume:
            self._volume = int(self._app_properties["volume"])
            updated_data[MediaAttr.VOLUME] = self._volume
            updated_data[KodiSensors.SENSOR_VOLUME] = self._volume
        if muted != self._app_properties["muted"]:
            self._is_volume_muted = self._app_properties["muted"]
            updated_data[MediaAttr.MUTED] = self._is_volume_muted
            updated_data[KodiSensors.SENSOR_VOLUME_MUTED] = self._is_volume_muted
        if updated_data:
            self.events.emit(Events.UPDATE, self.id, updated_data)

    # pylint: disable = W0613
    def on_key_press(self, sender: str, data: dict[str, Any]):
        """Handle a incoming key press notification."""
        _LOG.debug("[%s] Keypress %s %s", self.device_config.address, sender, data)

    # pylint: disable = W0613
    async def on_quit(self, sender: str, data: dict[str, Any]):
        """Reset the player state on quit action."""
        await self._clear_connection()

    def on_property_changed(self, sender: str, data: dict[str, Any]):
        """Handle player property change."""
        _LOG.debug("[%s] Kodi property changed %s", self.device_config.address, data)
        if all(
            x in ["currentaudiostream", "currentsubtitle", "subtitleenabled", "currentvideostream"]
            for x in data.get("property", {}).keys()
        ):
            self.event_loop.create_task(self._update_streams(data))

    def _get_language(self, info: dict[str, Any], language_first: bool) -> str:
        """Retrieve language name."""
        if language_first:
            language = _get_language_name(info.get("language", ""), self._app_language).title()
            if language != "":
                return language
            return info.get("name", "").title()
        language = info.get("name", "").title()
        if language != "":
            return language
        return _get_language_name(info.get("language", ""), self._app_language).title()

    def get_streams_info(self, properties: dict[str, Any]) -> str | None:
        """Build audio/subtitles stream info."""
        if self.device_config.show_stream_name:
            current_audio_stream: dict[str, Any] = properties.get("currentaudiostream", {})
            current_subtitle: dict[str, Any] = properties.get("currentsubtitle", {})
            subtitles_enabled: bool = properties.get("subtitleenabled", False)
            audio_stream = self._get_language(current_audio_stream, self.device_config.show_stream_language_name)
            subtitle_stream = ""
            if subtitles_enabled:
                subtitle_stream = self._get_language(current_subtitle, self.device_config.show_stream_language_name)
                if current_subtitle.get("isforced", False):
                    subtitle_stream += " (forced)"
                if current_subtitle.get("isimpaired", False):
                    subtitle_stream += " (impaired)"
            if audio_stream != "" or subtitle_stream != "":
                _LOG.debug(
                    "Audio/subtitles : %s, %s (enabled : %s)",
                    current_audio_stream,
                    current_subtitle,
                    subtitles_enabled,
                )
            info: list[str] = []
            if audio_stream != "":
                info.append(audio_stream)
            if subtitle_stream != "":
                info.append(subtitle_stream)
            return " - ".join(info)
        return None

    def get_streams_name(self, properties: dict[str, Any]) -> str | None:
        """Build audio/subtitles stream names."""
        if self.device_config.show_stream_name:
            current_audio_stream: dict[str, Any] = properties.get("currentaudiostream", {})
            current_subtitle: dict[str, Any] = properties.get("currentsubtitle", {})
            subtitles_enabled: bool = properties.get("subtitleenabled", properties.get("subtitleenabled", False))
            audio_stream = self._get_language(current_audio_stream, False)
            subtitle_stream = ""
            if subtitles_enabled:
                subtitle_stream = self._get_language(current_subtitle, False)
                if current_subtitle.get("isforced", False):
                    subtitle_stream += " (forced)"
                if current_subtitle.get("isimpaired", False):
                    subtitle_stream += " (impaired)"
            info: list[str] = []
            if audio_stream != "":
                info.append(audio_stream)
            if subtitle_stream != "":
                info.append(subtitle_stream)
            return " - ".join(info)
        return None

    @debounce(1)
    async def _update_streams(self, data: dict[str, Any]):
        """Debounce update stream to get the whole data."""
        await self._update_states(deferred=0, received_data=data)

    async def display_temporary_title(self, temporary_title: str):
        """Display a temporary title."""
        self._temporary_title = temporary_title
        # self.events.emit(Events.UPDATE, self.id, {
        #     MediaAttr.MEDIA_TITLE: self._temporary_title
        # })
        await self._display_temporary_title()

    @debounce(5)
    async def _display_temporary_title(self):
        self._temporary_title = None
        self.events.emit(Events.UPDATE, self.id, {MediaAttr.MEDIA_TITLE: self.media_title})

    def _register_ws_callbacks(self):
        _LOG.debug("[%s] Kodi register callbacks", self.device_config.address)
        self._kodi_connection.server.Player.OnPause = self.on_speed_event
        self._kodi_connection.server.Player.OnPlay = self.on_speed_event
        self._kodi_connection.server.Player.OnAVStart = self.on_speed_event
        self._kodi_connection.server.Player.OnAVChange = self.on_speed_event
        self._kodi_connection.server.Player.OnResume = self.on_speed_event
        self._kodi_connection.server.Player.OnSpeedChanged = self.on_speed_event
        self._kodi_connection.server.Player.OnSeek = self.on_speed_event
        self._kodi_connection.server.Player.OnPropertyChanged = self.on_property_changed
        self._kodi_connection.server.Player.OnStop = self.on_stop
        self._kodi_connection.server.Application.OnVolumeChanged = self.on_volume_changed
        # self._kodi_connection.server.Other.OnKeyPress = self.on_key_press
        self._kodi_connection.server.System.OnQuit = self.on_quit
        self._kodi_connection.server.System.OnRestart = self.on_quit
        self._kodi_connection.server.System.OnSleep = self.on_quit

    async def _register_callbacks(self):
        """Call after ws is connected."""
        self._connect_error = False
        self._register_ws_callbacks()
        # version = (await self._kodi.get_application_properties(["version"]))["version"]
        # f"{version['major']}.{version['minor']}"

    async def _clear_connection(self, close=True):
        """Close connection and reset state."""
        self._reset_state()
        if close:
            try:
                await self._kodi_connection.close()
            # pylint: disable = W0718
            except Exception:
                pass

    async def _ping(self):
        """Send websocket ping."""
        try:
            await self._kodi.ping()
        except (TransportError, CannotConnectError, ServerTimeoutError):
            if not self._connect_error:
                self._connect_error = True
                _LOG.warning("[%s] Unable to ping Kodi via websocket", self.device_config.address)
            await self._clear_connection()
        # pylint: disable = W0718
        except Exception as ex:
            _LOG.error("[%s] Unknown exception ping %s", self.device_config.address, ex)
        else:
            self._connect_error = False

    async def _reconnect_websocket_if_disconnected(self, *_) -> bool:
        """Reconnect the websocket if it fails."""
        if not self._kodi_connection.connected and self._reconnect_retry >= CONNECTION_RETRIES:
            return False
        if not self._kodi_connection.connected:
            self._reconnect_retry += 1
            self._available = False
            _LOG.debug(
                "[%s] Kodi websocket not connected, retry %s / %s",
                self._device_config.address,
                self._reconnect_retry,
                CONNECTION_RETRIES,
            )
            # Connection status result has to be reset if connection fails and future result is still okay
            if not self._connection_status or self._connection_status.done():
                self._connection_status = self.event_loop.create_future()
            try:
                await asyncio.wait_for(shield(self.connect()), DEFAULT_TIMEOUT * 2)
            except asyncio.TimeoutError:
                _LOG.debug("[%s] Kodi websocket too slow to reconnect", self._device_config.address)
        else:
            if self._reconnect_retry > 0:
                self._reconnect_retry = 0
                _LOG.debug("[%s] Kodi websocket is connected", self.device_config.address)
            await self._ping()
        return True
        # _LOG.debug("Kodi websocket %s ping : %s", self._device_config.address, self._connect_error)

    def exception_handler(self, loop, context):
        """Handle exception for running loop."""
        if not context or context.get("exception", None) is None:
            return
        exception = context.get("exception", None)
        message = context.get("message", None)
        if message is None:
            message = ""
        # log exception
        _LOG.error(f"[%s] Websocket task failed, msg={message}, exception={exception}", self.device_config.address)

    async def start_watchdog(self):
        """Start websocket watchdog."""
        while True:
            await asyncio.sleep(WEBSOCKET_WATCHDOG_INTERVAL)
            try:
                if not await self._reconnect_websocket_if_disconnected():
                    _LOG.debug("[%s] Stop watchdog", self.device_config.address)
                    self._websocket_task = None
                    break
            # pylint: disable = W0718
            except Exception as ex:
                _LOG.error("[%s] Unknown exception %s", self.device_config.address, ex)

    async def connect(self) -> bool:
        """Connect to Kodi via websocket protocol."""
        # pylint: disable = R0915
        try:
            if self._connect_lock.locked():
                _LOG.debug("[%s] Connect already in progress, returns", self.device_config.address)
                return True
            _LOG.debug("[%s] Connecting", self.device_config.address)
            await self._connect_lock.acquire()
            if self._kodi_connection and self._kodi_connection.connected:
                _LOG.debug("[%s] Already connected", self.device_config.address)
                return True
            self._connect_error = False

            await self.init_connection()
            # This method was buggy, this is the reason why pykodi library has been integrated into the driver
            # TODO report the fix
            await self._kodi_connection.connect()
            await self._register_callbacks()
            await self._ping()
            await self._update_states()

            _LOG.debug("[%s] Connection successful", self._device_config.address)
            if self._websocket_task is None:
                self._websocket_task = self.event_loop.create_task(self.start_watchdog())
            if self._connection_status and not self._connection_status.done():
                self._connection_status.set_result(True)
            if self._device_config.media_update_task and self._update_position_task is None:
                self._update_position_task = self.event_loop.create_task(self.start_update_position_task())
            elif not self._device_config.media_update_task and self._update_position_task is not None:
                try:
                    self._update_position_task.cancel()
                # pylint: disable = W0718
                except Exception as ex:
                    _LOG.error("[%s] Failed to cancel update task %s", self.device_config.address, ex)
                self._update_position_task = None
        except (TransportError, CannotConnectError, ServerTimeoutError) as ex:
            _LOG.debug("[%s] Connection error : %s", self.device_config.address, ex)
            try:
                # In case of OSError it means that the connection is not ready, let's wait a little bit
                if len(ex.args) > 1 and isinstance(ex.args[1], ClientOSError):
                    _LOG.warning("[%s] OS error, waiting %ss", self.device_config.address, ERROR_OS_WAIT)
                    await asyncio.sleep(ERROR_OS_WAIT)
            # pylint: disable = W0718
            except Exception:
                pass

            if not self._connection_status or self._connection_status.done():
                self._connection_status = self.event_loop.create_future()
            if not self._connect_error:
                self._connect_error = True
                _LOG.warning("[%s] Unable to connect to Kodi via websocket", self.device_config.address)
                # , ex, stack_info=True, exc_info=True)
            await self._clear_connection(False)
            return False
        # pylint: disable = W0718
        except Exception as ex:
            _LOG.error("[%s] Unknown exception connect : %s", self.device_config.address, ex)
            return False
        finally:
            if self._reconnect_retry >= CONNECTION_RETRIES and self._connect_error:
                _LOG.debug("[%s] Kodi websocket not connected, abort retries", self.device_config.address)
                if self._websocket_task:
                    try:
                        self._websocket_task.cancel()
                    except Exception as ex:
                        _LOG.error("[%s] Failed to cancel websocket task %s", self.device_config.address, ex)
                    self._websocket_task = None
            elif self._websocket_task is None:
                self._websocket_task = self.event_loop.create_task(self.start_watchdog())
            self._available = True
            self.events.emit(Events.CONNECTED, self.id)
            try:
                if self._connect_lock.locked():
                    self._connect_lock.release()
            except RuntimeError:
                pass
        return True

    async def disconnect(self):
        """Disconnect from TV."""
        _LOG.debug("[%s] Disconnect %s", self.device_config.address, self.id)
        try:
            if self._websocket_task:
                self._websocket_task.cancel()
            if self._kodi_connection:
                await self._kodi_connection.close()
                self._kodi_connection = None
            self._attr_state = MediaStates.OFF
        except CannotConnectError as er:
            _LOG.error(
                "[%s] Logout failed cannot connect: [%s]",
                self.device_config.address,
                er,
            )
        except InvalidAuthError as error:
            _LOG.error(
                "[%s] Logout failed: [%s]",
                self.device_config.address,
                error,
            )
        finally:
            self._available = False
            self._websocket_task = None
            self._app_language = None
            self._reconnect_retry = 0
            try:
                self._update_lock.release()
            except RuntimeError:
                pass

    def _reset_state(self, players=None):
        # pylint: disable = R0915
        self._players = players
        self._properties = {}
        self._item = {}
        self._app_properties = {}
        self._media_position = None
        self._media_position_updated_at = None
        self._temporary_title = None
        self._update_state_retry = 0
        self._chapters = None
        self._source = None
        self._audio_stream = ""
        self._subtitle_stream = ""
        try:
            self._update_lock.release()
        except RuntimeError:
            pass

    async def start_update_position_task(self):
        """Start websocket watchdog."""
        while True:
            await asyncio.sleep(UPDATE_POSITION_INTERVAL)
            try:
                await self._update_position()
            # pylint: disable = W0718
            except Exception as ex:
                _LOG.error("[%s] Unknown exception %s", self.device_config.address, ex)

    @debounce(2)
    async def _update_position(self) -> None:
        if (
            self._position_timestamp is not None
            and self._position_timestamp + float(UPDATE_POSITION_INTERVAL - 10) > time.time()
        ):
            return
        if (
            not self._kodi_connection.connected
            or self._update_lock.locked()
            or self._kodi_is_off
            or self._players is None
            or len(self._players) == 0
        ):
            return
        await self._update_states()

    async def _reset_media_artwork(self):
        """Emit artwork data only."""
        updated_data = {MediaAttr.MEDIA_IMAGE_URL: self.media_artwork}
        _LOG.debug("[%s] Emit of artwork %s", self.device_config.address, updated_data)
        self.events.emit(Events.UPDATE, self.id, updated_data)
        await asyncio.sleep(0)

    # pylint: disable = R0914,R0915
    async def _update_states(self, deferred=0, received_data: dict[str, Any] | None = None) -> None:
        """Update entity state attributes."""
        if deferred > 0:
            await asyncio.sleep(deferred)

        if received_data is None:
            received_data = {}

        if not self._kodi_connection.connected:
            _LOG.debug("[%s] Update states requested but not connected", self.device_config.address)
            self._reset_state()
            return

        if self._update_lock.locked():
            _LOG.debug("[%s] Update states already locked", self.device_config.address)
            if time.time() - self._update_lock_time > UPDATE_LOCK_TIMEOUT:
                _LOG.warning(
                    "[%s] Update is locked since a too long time, unlock it anyway", self._device_config.address
                )
                try:
                    self._update_lock.release()
                except RuntimeError:
                    pass
            else:
                return
        _LOG.debug("[%s] Update states in progress", self.device_config.address)
        await self._update_lock.acquire()
        self._update_lock_time = time.time()
        updated_data = {}

        # pylint: disable = R1702
        try:
            self._players = await self._kodi.get_players()
            if self._kodi_is_off:
                current_state = self.state
                self._reset_state()
                if current_state != self.state:
                    self.events.emit(Events.UPDATE, self.id, {MediaAttr.STATE: self.state})
                try:
                    self._update_lock.release()
                except RuntimeError:
                    pass
                return

            if self._players and len(self._players) > 0:
                self._app_properties = await self._kodi.get_application_properties(["volume", "muted"])
                volume = int(self._app_properties["volume"])
                if self._volume != volume:
                    self._volume = volume
                    updated_data[MediaAttr.VOLUME] = self._volume
                muted = self._app_properties["muted"]
                if muted != self._is_volume_muted:
                    self._is_volume_muted = muted
                    updated_data[MediaAttr.MUTED] = muted

                if self._app_language is None:
                    self._app_language = await self.get_app_language()

                # Save current values before update to check changes
                current_video_info = self.video_info
                current_audio_info = self.audio_info

                self._properties = await self._kodi.get_player_properties(
                    self._players[0],
                    [
                        "time",
                        "totaltime",
                        "speed",
                        "live",
                        "currentaudiostream",
                        "currentsubtitle",
                        "subtitleenabled",
                        "audiostreams",
                        "subtitles",
                        "currentvideostream",
                    ],
                )
                if self._device_config.log_additional_data:
                    _LOG.debug("[%s] Updated properties %s", self.device_config.address, self._properties)

                position = self._properties["time"]
                if position:
                    media_position = position["hours"] * 3600 + position["minutes"] * 60 + position["seconds"]
                else:
                    media_position = 0
                if self._media_position != media_position or self._media_position_updated_at is None:
                    self._media_position = media_position
                    updated_data[MediaAttr.MEDIA_POSITION] = media_position
                    self._media_position_updated_at = datetime.datetime.now(datetime.timezone.utc)
                    updated_data["media_position_updated_at"] = self.media_position_updated_at

                totaltime = self._properties["totaltime"]
                if totaltime:
                    duration = totaltime["hours"] * 3600 + totaltime["minutes"] * 60 + totaltime["seconds"]
                else:
                    duration = 0
                if self._media_duration != duration:
                    self._media_duration = duration
                    updated_data[MediaAttr.MEDIA_POSITION] = self.media_position
                    updated_data[MediaAttr.MEDIA_DURATION] = duration

                if current_video_info != self.video_info:
                    updated_data[KodiSensors.SENSOR_VIDEO_INFO] = self.video_info

                if current_audio_info != self.audio_info:
                    updated_data[KodiSensors.SENSOR_AUDIO_INFO] = self.audio_info

                self._item = await self._kodi.get_playing_item_properties(
                    self._players[0],
                    [
                        "title",
                        "file",
                        "uniqueid",
                        "thumbnail",
                        "fanart",
                        "art",
                        "artist",
                        "albumartist",
                        "showtitle",
                        "album",
                        "season",
                        "episode",
                        "track",
                        # "streamdetails"
                    ],
                )

                _LOG.debug("[%s] Kodi extracted properties : %s", self.device_config.address, self._item)

                item_type = KODI_MEDIA_TYPES.get(self._item.get("type"), MediaType.VIDEO)
                if item_type != self._media_type:
                    self._media_type = item_type
                    updated_data[MediaAttr.MEDIA_TYPE] = self.media_type

                art = self._item.get("art", {})
                if self.media_type == MediaType.TVSHOW:
                    artwork_type = self._device_config.artwork_type_tvshows
                else:
                    artwork_type = self._device_config.artwork_type

                # Workaround for remote bug : when stopping/playing the same media or another media
                # with the same artwork it won't be displayed
                current_artwork = self.media_artwork
                is_starting_media = False
                # Playback state goes from stop (MediaStates.ON) to play
                if self._attr_state == self._attr_state == MediaStates.ON and self.get_state() in [
                    MediaStates.PLAYING,
                    MediaStates.BUFFERING,
                    MediaStates.PAUSED,
                ]:
                    is_starting_media = True

                thumbnail = art.get(artwork_type, None)
                if thumbnail is None and artwork_type == "fanart":
                    thumbnail = self._item.get("fanart")

                if thumbnail is None or thumbnail == "":
                    thumbnail = self._item.get("thumbnail", None)

                if thumbnail == "":
                    thumbnail = None

                if thumbnail != self._thumbnail:
                    self._thumbnail = thumbnail
                    self._media_image_url = self._kodi.thumbnail_url(thumbnail) or ""
                    self._media_image_data = ""
                    # Not working with smb links.
                    # TODO extend this approach for other media types
                    if self._item["type"] == "movie" and "@smb" in thumbnail:
                        try:
                            result = await self._kodi.call_method(
                                "VideoLibrary.GetAvailableArt",
                                **{"item": {"movieid": self._item["id"]}, "arttype": "poster"},
                            )
                            if result and len(result["availableart"]) > 0:
                                self._media_image_url = result["availableart"][0]["url"] or ""
                                self._media_image_url = self._media_image_url.removeprefix("image://").removesuffix("/")
                                self._media_image_url = urllib.parse.unquote(self._media_image_url)
                        # pylint: disable = W0718
                        except Exception as ex:
                            _LOG.info(
                                "[%s] Kodi please report faulty thumbnail analysis %s : %s (%s)",
                                self.device_config.address,
                                thumbnail,
                                self._media_image_url,
                                ex,
                            )
                    if self._device_config.download_artwork:
                        try:
                            async with ClientSession() as session:
                                async with session.get(self._media_image_url, timeout=ARTWORK_TIMEOUT) as response:
                                    buffer = b""
                                    async for data, _ in response.content.iter_chunks():
                                        buffer += data
                                    self._media_image_data = (
                                        "data:"
                                        + response.content_type
                                        + ";base64,"
                                        + base64.b64encode(buffer).decode("utf-8")
                                    )
                        # pylint: disable = W0718
                        except Exception as ex:
                            _LOG.warning("[%s] Failed to download artwork : %s", self.device_config.address, ex)
                            self._media_image_data = ""

                    _LOG.debug(
                        "[%s] Kodi changed thumbnail %s : %s",
                        self.device_config.address,
                        self._thumbnail,
                        self.media_artwork,
                    )
                    # self._media_image_url = self._media_image_url.removesuffix('%2F')
                    updated_data[MediaAttr.MEDIA_IMAGE_URL] = self.media_artwork

                media_title = self._item.get("title") or self._item.get("label") or self._item.get("file")
                if self.device_config.show_stream_name:
                    streams_name = self.get_streams_name(self._properties)
                    if streams_name and streams_name != "":
                        await self.display_temporary_title(streams_name)

                changed_media = False
                if media_title != self._media_title:
                    _LOG.debug("[%s] Changed media : %s", self.device_config.address, media_title)
                    self._media_title = media_title
                    updated_data[MediaAttr.MEDIA_TITLE] = self._media_title
                    changed_media = True

                artists = self._item.get("artist")
                season: int | None = self._item.get("season")
                episode: int | None = self._item.get("episode")
                if artists and len(artists) > 0:
                    media_artist = artists[0]
                elif (season and season > 0) or (episode and episode > 0):
                    media_artist = ""
                    if season and season > 0:
                        media_artist = "S" + str(season)
                    if episode and episode > 0:
                        media_artist += "E" + str(episode)
                else:
                    media_artist = ""

                if media_artist == "":
                    media_artist = self.get_streams_info(self._properties)

                if media_artist != self._media_artist:
                    self._media_artist = media_artist
                    updated_data[MediaAttr.MEDIA_ARTIST] = self._media_artist
                    changed_media = True

                media_album = self._item.get("album")
                if media_album != self._media_album:
                    self._media_album = media_album
                    updated_data[MediaAttr.MEDIA_ALBUM] = self._media_album
                    changed_media = True

                if is_starting_media and len(self.media_artwork) > 0 and current_artwork == self.media_artwork:
                    _LOG.debug(
                        "[%s] Starting new media but unchanged artwork, sending empty artwork to reset it",
                        self.device_config.address,
                    )
                    await self._reset_media_artwork()

                # If media changed, update chapters list (Kodi >=22)
                current_chapter = self.current_chapter
                if changed_media:
                    self._chapters = None
                    try:
                        data = await self.get_chapters()
                        if data and (chapters := data.get("chapters", [])):
                            self._chapters = chapters
                            current_chapter = self.current_chapter
                            updated_data[KodiSelects.SELECT_CHAPTER] = {
                                SelectAttributes.CURRENT_OPTION: current_chapter if current_chapter else "",
                                SelectAttributes.OPTIONS: (
                                    [x.get("name", "") for x in self.chapters] if self.chapters else []
                                ),
                            }
                            if current_chapter:
                                _LOG.debug(
                                    "[%s] Found chapter name to display %s", self.device_config.address, current_chapter
                                )
                                await self.display_temporary_title(current_chapter)
                    # pylint: disable = W0718
                    except Exception:
                        pass
                        # _LOG.debug("[%s] Could not extract chapters %s", self.device_config.address, ex)

                    if self._temporary_title:
                        updated_data[MediaAttr.MEDIA_TITLE] = self._temporary_title
                    updated_data[MediaAttr.SOURCE_LIST] = self.source_list
                    updated_data[MediaAttr.SOUND_MODE_LIST] = [
                        track.get_track_name(KodiStreamConfig(self._device_config.sensor_audio_stream_config))
                        for track in self.audio_tracks
                    ]
                    updated_data[KodiSelects.SELECT_AUDIO_STREAM] = {
                        SelectAttributes.OPTIONS: [
                            x.get_track_name(KodiStreamConfig(self._device_config.sensor_audio_stream_config))
                            for x in self.audio_tracks
                        ]
                    }
                    updated_data[KodiSelects.SELECT_SUBTITLE_STREAM] = {
                        SelectAttributes.OPTIONS: [
                            x.get_track_name(KodiStreamConfig(self._device_config.sensor_subtitle_stream_config))
                            for x in self.subtitle_tracks
                        ]
                    }

                if self.state == MediaStates.PAUSED and current_chapter:
                    await self.display_temporary_title(current_chapter)
                    updated_data[MediaAttr.MEDIA_TITLE] = self._temporary_title

                if self._source != current_chapter:
                    self._source = current_chapter
                    updated_data[MediaAttr.SOURCE] = current_chapter
                    await self.display_temporary_title(current_chapter)
                    updated_data[MediaAttr.MEDIA_TITLE] = self._temporary_title
                    updated_data[KodiSensors.SENSOR_CHAPTER] = self.current_chapter

                new_audio_track = self.current_audio_track
                if (
                    new_audio_track
                    and self._audio_stream
                    != new_audio_track.get_track_name(KodiStreamConfig(self._device_config.sensor_audio_stream_config))
                ) or (new_audio_track is None and self._audio_stream != ""):
                    self._audio_stream = (
                        new_audio_track.get_track_name(KodiStreamConfig(self._device_config.sensor_audio_stream_config))
                        if new_audio_track
                        else ""
                    )
                    updated_data[MediaAttr.SOUND_MODE] = self._audio_stream
                    updated_data[KodiSensors.SENSOR_AUDIO_STREAM] = self.sensor_audio_stream
                    select_info = updated_data.get(KodiSelects.SELECT_AUDIO_STREAM, {})
                    select_info[SelectAttributes.CURRENT_OPTION] = self.selector_audio_stream
                    updated_data[KodiSelects.SELECT_AUDIO_STREAM] = select_info

                if self._subtitle_stream != self.current_subtitle_track.get_track_name(
                    KodiStreamConfig(self._device_config.sensor_subtitle_stream_config)
                ):
                    self._subtitle_stream = self.current_subtitle_track.get_track_name(
                        KodiStreamConfig(self._device_config.sensor_subtitle_stream_config)
                    )
                    updated_data[KodiSensors.SENSOR_SUBTITLE_STREAM] = self.sensor_subtitle_stream
                    select_info = updated_data.get(KodiSelects.SELECT_SUBTITLE_STREAM, {})
                    select_info[SelectAttributes.CURRENT_OPTION] = self.selector_subtitle_stream
                    updated_data[KodiSelects.SELECT_SUBTITLE_STREAM] = select_info

                current_state = self._attr_state
                if current_state != self.get_state():
                    updated_data[MediaAttr.STATE] = self.get_state()

                # If media changed, request a deferred artwork update as it may not be available at this time
                if changed_media and len(self.media_artwork) == 0:
                    deferred = 4
                    _LOG.debug(
                        '[%s] Kodi changed media to "%s" but artwork is empty, will try again in %s seconds',
                        self.device_config.address,
                        media_title,
                        deferred,
                    )
                    asyncio.create_task(self._update_states(deferred=deferred))

            else:
                self._reset_state([])
                self._media_position = 0
                self._media_duration = 0
                self._media_title = ""
                self._media_album = ""
                self._media_artist = ""
                updated_data[MediaAttr.MEDIA_POSITION] = 0
                updated_data[MediaAttr.MEDIA_DURATION] = 0
                updated_data[MediaAttr.MEDIA_TITLE] = ""
                updated_data[MediaAttr.MEDIA_ALBUM] = ""
                updated_data[MediaAttr.MEDIA_ARTIST] = ""
                updated_data[MediaAttr.SOURCE] = ""
                updated_data[MediaAttr.SOURCE_LIST] = []
                updated_data[MediaAttr.SOUND_MODE_LIST] = []
                updated_data[KodiSensors.SENSOR_AUDIO_STREAM] = ""
                updated_data[KodiSensors.SENSOR_SUBTITLE_STREAM] = ""
                updated_data[KodiSensors.SENSOR_CHAPTER] = ""
                updated_data[KodiSensors.SENSOR_VIDEO_INFO] = ""
                updated_data[KodiSensors.SENSOR_AUDIO_INFO] = ""
                updated_data[KodiSensors.SENSOR_VOLUME] = self._volume
                updated_data[KodiSensors.SENSOR_VOLUME_MUTED] = self.is_volume_muted
                updated_data[KodiSelects.SELECT_SUBTITLE_STREAM] = {
                    SelectAttributes.CURRENT_OPTION: "",
                    SelectAttributes.OPTIONS: [],
                }
                updated_data[KodiSelects.SELECT_AUDIO_STREAM] = {
                    SelectAttributes.CURRENT_OPTION: "",
                    SelectAttributes.OPTIONS: [],
                }
                updated_data[KodiSelects.SELECT_CHAPTER] = {
                    SelectAttributes.CURRENT_OPTION: "",
                    SelectAttributes.OPTIONS: [],
                }

            self._position_timestamp = time.time()
            if self._attr_state != self.get_state():
                self._attr_state = self.get_state()
                updated_data[MediaAttr.STATE] = self.get_state()

            if updated_data:
                self.events.emit(Events.UPDATE, self.id, updated_data)
            self._update_state_retry = 0
        except TimeoutError as timeout_error:
            if self._update_state_retry < UPDATE_STATE_RETRY:
                self._update_state_retry += 1
                _LOG.info(
                    "[%s] Update states : timeout error, retry %s : %s",
                    self.device_config.address,
                    self._update_state_retry,
                    timeout_error,
                )
                asyncio.create_task(self._update_states(deferred=1))
            else:
                _LOG.info(
                    "[%s] Update states : timeout error : %s %s",
                    self.device_config.address,
                    self._update_state_retry,
                    timeout_error,
                )
                self._update_state_retry = 0
        # pylint: disable = W0718
        except Exception as ex:
            _LOG.info(
                "[%s] Update states : unknown error : %s",
                self.device_config.address,
                ex,
            )
        try:
            self._update_lock.release()
        except RuntimeError:
            pass

    @property
    def server(self) -> jsonrpc_base.Server | None:
        """Return Kodi server."""
        if self._kodi is None:
            return None
        return self._kodi.server

    @property
    def kodi_connection(self) -> KodiWSConnection | None:
        """Return current Kodi Websocket connection."""
        return self._kodi_connection

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the device attributes."""
        attributes = {
            MediaAttr.STATE: self.get_state(),
            MediaAttr.MUTED: self.is_volume_muted,
            MediaAttr.VOLUME: self.volume_level,
            MediaAttr.MEDIA_TYPE: self.media_type,
            MediaAttr.MEDIA_IMAGE_URL: self.media_image_url if self.media_image_url else "",
            MediaAttr.MEDIA_TITLE: self.media_title if self.media_title else "",
            MediaAttr.MEDIA_ALBUM: self.media_album if self.media_album else "",
            MediaAttr.MEDIA_ARTIST: self.media_artist if self.media_artist else "",
            MediaAttr.MEDIA_POSITION: self.media_position,
            MediaAttr.MEDIA_DURATION: self.media_duration,
            MediaAttr.MEDIA_POSITION_UPDATED_AT: (
                self.media_position_updated_at if self.media_position_updated_at else ""
            ),
            MediaAttr.SOURCE_LIST: self.source_list,
            MediaAttr.SOURCE: self.source if self.source_list else "",
            MediaAttr.SOUND_MODE_LIST: [
                track.get_track_name(KodiStreamConfig(self._device_config.sensor_audio_stream_config))
                for track in self.audio_tracks
            ],
            MediaAttr.SOUND_MODE: (
                self.current_audio_track.get_track_name(
                    KodiStreamConfig(self._device_config.sensor_audio_stream_config)
                )
                if self.current_audio_track
                else ""
            ),
            KodiSensors.SENSOR_AUDIO_STREAM: self.sensor_audio_stream,
            KodiSensors.SENSOR_SUBTITLE_STREAM: self.sensor_subtitle_stream,
            KodiSensors.SENSOR_CHAPTER: self.current_chapter if self.current_chapter else "",
            KodiSensors.SENSOR_VIDEO_INFO: self.video_info,
            KodiSensors.SENSOR_AUDIO_INFO: self.audio_info,
            KodiSensors.SENSOR_VOLUME: self._volume,
            KodiSensors.SENSOR_VOLUME_MUTED: self.is_volume_muted,
            KodiSelects.SELECT_SUBTITLE_STREAM: {
                SelectAttributes.CURRENT_OPTION: self.selector_subtitle_stream,
                SelectAttributes.OPTIONS: [
                    x.get_track_name(KodiStreamConfig(self._device_config.sensor_subtitle_stream_config))
                    for x in self.subtitle_tracks
                ],
                SelectAttributes.STATE: SelectStates.ON,
            },
            KodiSelects.SELECT_AUDIO_STREAM: {
                SelectAttributes.CURRENT_OPTION: self.selector_audio_stream,
                SelectAttributes.OPTIONS: [
                    x.get_track_name(KodiStreamConfig(self._device_config.sensor_audio_stream_config))
                    for x in self.audio_tracks
                ],
                SelectAttributes.STATE: SelectStates.ON,
            },
            KodiSelects.SELECT_CHAPTER: {
                SelectAttributes.CURRENT_OPTION: self.current_chapter if self.current_chapter else "",
                SelectAttributes.OPTIONS: [x.get("name", "") for x in self.chapters] if self.chapters else [],
                SelectAttributes.STATE: SelectStates.ON,
            },
        }
        return attributes

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self._available

    @property
    def device_config(self) -> KodiConfigDevice:
        """Return device configuration."""
        return self._device_config

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
    def state(self) -> MediaStates:
        """Return the cached state of the device."""
        return self.get_state()

    @property
    def connection_status(self) -> Future | None:
        """Return the connection status."""
        return self._connection_status

    @property
    def supported_features(self) -> list[Features]:
        """Return supported features."""
        return self._supported_features

    @property
    def media_position(self):
        """Return current media position."""
        return self._media_position

    @property
    def media_position_updated_at(self) -> str | None:
        """Return timestamp of urrent media position."""
        if self._media_position_updated_at:
            return self._media_position_updated_at.isoformat()
        return None

    @property
    def current_media_position(self):
        """Return calculated media position."""
        if self.state != MediaStates.PLAYING or self._media_position_updated_at is None:
            return self.media_position
        elapsed_time = datetime.datetime.now(datetime.timezone.utc) - self._media_position_updated_at
        position = self.media_position + elapsed_time.seconds
        if self.media_duration > 0 and position < self.media_duration:
            return position
        return self.media_position

    @property
    def media_duration(self):
        """Return current media duration."""
        return self._media_duration

    @property
    def source_list(self) -> list[str]:
        """Return a list of available input sources."""
        if self._chapters is None:
            return []
        return [chapter.get("name", "") for chapter in self._chapters]

    @staticmethod
    def _get_stream_info(stream: dict[str, Any]) -> str:
        """Return stream info."""
        bitrate = stream.get("bitrate", 0)
        channels = stream.get("channels", 0)
        codec = stream.get("codec", "")
        samplerate = stream.get("samplerate", 0)
        stream_info = ""
        if codec:
            stream_info = codec.title()
            if bitrate > 0:
                stream_info = f"{stream_info} {int(bitrate/1000)}kbps"
            if channels > 0:
                stream_info = f"{stream_info} {channels} channels"
            if samplerate > 0:
                stream_info = f"{stream_info} {samplerate}Hz"
        return stream_info

    @property
    def audio_tracks(self) -> list[Track]:
        """Return a list of available audio tracks."""
        tracks: list[Track] = []
        streams: list[dict[str, Any]] = self._properties.get("audiostreams", [])
        duplicates = False
        for stream in streams:
            stream_name = stream.get("name", "")
            if not stream_name:
                stream_name = KodiDevice._get_stream_info(stream)

            language_name = stream.get("language", "")
            if language_name:
                language_name = _get_language_name(language_name, self._app_language)
            index = stream.get("index", 0)
            track = Track(index=index, language_name=language_name, stream_name=stream_name)
            if track.get_track_name(KodiStreamConfig(self._device_config.sensor_audio_stream_config)) in [
                x.get_track_name(KodiStreamConfig(self._device_config.sensor_audio_stream_config)) for x in tracks
            ]:
                duplicates = True
            tracks.append(track)
        if duplicates:
            for track in tracks:
                track.stream_name = f"{track.index}:{track.stream_name}"
        return tracks

    @property
    def subtitle_tracks(self) -> list[Track]:
        """Return a list of available subtitle tracks."""
        tracks: list[Track] = [Track.get_disabled_track(self._app_language)]
        streams: list[dict[str, Any]] = self._properties.get("subtitles", [])
        duplicates = False
        for stream in streams:
            stream_name = stream.get("name", "")
            language_name = stream.get("language", "")
            if language_name:
                language_name = _get_language_name(language_name, self._app_language)
            index = stream.get("index", 0)
            isdefault = stream.get("isdefault", False)
            isforced = stream.get("isforced", False)
            isimpaired = stream.get("isimpaired", False)
            track = Track(
                index=index,
                language_name=language_name,
                stream_name=stream_name,
                forced=isforced,
                impaired=isimpaired,
                default=isdefault,
            )
            if track.get_track_name(KodiStreamConfig(self._device_config.sensor_audio_stream_config)) in [
                x.get_track_name(KodiStreamConfig(self._device_config.sensor_audio_stream_config)) for x in tracks
            ]:
                duplicates = True
            tracks.append(track)
        if duplicates:
            for track in tracks:
                track.stream_name = f"{track.index}:{track.stream_name}"
        return tracks

    @property
    def current_audio_track(self) -> Track | None:
        """Return the current audio track name."""
        current_audio_stream = self._properties.get("currentaudiostream", {})
        if current_audio_stream is None:
            return None
        for track in self.audio_tracks:
            if track.index == current_audio_stream.get("index", 0):
                return track
        return None

    @property
    def sensor_audio_stream(self) -> str:
        """Return the sensor audio stream."""
        current_track = self.current_audio_track
        if current_track is None:
            return ""
        return current_track.get_track_name(KodiStreamConfig(self.device_config.sensor_audio_stream_config))

    @property
    def current_subtitle_track(self) -> Track:
        """Return the current subtitle track name."""
        subtitles_enabled: bool = self._properties.get("subtitleenabled", False)
        if not subtitles_enabled:
            return Track.get_disabled_track(self._app_language)
        current_subtitle_stream: dict[str, Any] = self._properties.get("currentsubtitle", {})
        if current_subtitle_stream is None:
            return Track.get_disabled_track(self._app_language)
        language_name = _get_language_name(current_subtitle_stream.get("language", ""), self._app_language)
        stream_name = current_subtitle_stream.get("name", "")
        index = current_subtitle_stream.get("index", 0)
        track = Track(language_name=language_name, stream_name=stream_name, index=index)
        if current_subtitle_stream.get("isforced", False):
            track.forced = True
        if current_subtitle_stream.get("isimpaired", False):
            track.impaired = True
        if current_subtitle_stream.get("isdefault", False):
            track.default = True
        return track

    @property
    def sensor_subtitle_stream(self) -> str:
        """Return the sensor subtitle stream."""
        current_track = self.current_subtitle_track
        if current_track is None:
            return ""
        return current_track.get_track_name(KodiStreamConfig(self.device_config.sensor_subtitle_stream_config))

    @property
    def selector_subtitle_stream(self) -> str:
        """Return the sensor subtitle stream."""
        return self.sensor_subtitle_stream

    @property
    def selector_audio_stream(self) -> str:
        """Return the sensor subtitle stream."""
        return self.sensor_audio_stream

    @property
    def source(self) -> str:
        """Return the current input source."""
        return self.current_chapter

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
    def media_artwork(self) -> str:
        """Media artwork depending on device configuration."""
        if self._device_config.download_artwork:
            return self._media_image_data
        return self.media_image_url

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
        """Return current media type."""
        return self._media_type

    @property
    def player_id(self) -> int:
        """Return current player ID."""
        return self._players[0]["playerid"]

    @property
    def chapters(self) -> list[dict[str, Any]]:
        """Return chapters list."""
        return self._chapters

    @property
    def current_chapter(self) -> str | None:
        """Current chapter title."""
        if self._chapters is None or len(self._chapters) == 0:
            return None
        position = self.current_media_position
        found_chapter = self._chapters[0]
        for chapter in self._chapters:
            if position <= chapter.get("time", 0):
                break
            found_chapter = chapter
        return found_chapter.get("name", "")

    @property
    def video_info(self) -> str:
        """Video information."""
        video_stream = self._properties.get("currentvideostream", None)
        if video_stream is None:
            return ""
        # pylint: disable=W1405
        return f"{video_stream.get('width', 0)}x{video_stream.get('height', 0)} {video_stream.get('codec', '')}"

    @property
    def audio_info(self) -> str:
        """Audio information."""
        current_audio_stream = self._properties.get("currentaudiostream", {})
        if not current_audio_stream:
            return ""
        return KodiDevice._get_stream_info(current_audio_stream)

    @retry()
    async def set_volume_level(self, volume: float | None):
        """Set volume level, range 0..100."""
        if volume is None:
            return ucapi.StatusCodes.BAD_REQUEST
        _LOG.debug("[%s] Kodi setting volume to %s", self.device_config.address, volume)
        await self._kodi.set_volume_level(int(volume))
        return ucapi.StatusCodes.OK

    @retry()
    async def volume_up(self):
        """Send volume-up command to Kodi."""
        await self._kodi.volume_up()

    @retry()
    async def volume_down(self):
        """Send volume-down command to Kodi."""
        await self._kodi.volume_down()

    @retry()
    async def mute(self, muted: bool):
        """Send mute command to Kodi."""
        _LOG.debug("[%s] Sending mute: %s", self.device_config.address, muted)
        await self._kodi.mute(muted)

    async def async_media_play(self):
        """Send play command."""
        await self._kodi.play()

    async def async_media_pause(self):
        """Send media pause command to media player."""
        await self._kodi.pause()

    @retry()
    async def play_pause(self):
        """Send toggle-play-pause command to Kodi."""
        self._position_timestamp = None
        try:
            self._players = await self._kodi.get_players()
            await self._kodi.call_method("Player.PlayPause", **{"playerid": self.player_id})
        # pylint: disable = W0718
        except Exception:
            if self._properties.get("speed", 0) == 0:
                await self.async_media_play()
            else:
                await self.async_media_pause()
        await self._update_position()

    @retry()
    async def stop(self):
        """Send stop command to Kodi."""
        await self._kodi.stop()

    @retry()
    async def next(self):
        """Send next-track command to Kodi."""
        await self._kodi.next_track()

    @retry()
    async def previous(self):
        """Send previous-track command to Kodi."""
        await self._kodi.previous_track()

    @retry()
    async def media_seek(self, position: float):
        """Send seek command."""
        await self._kodi.media_seek(position)

    @retry()
    async def context_menu(self):
        """Send display context menu command."""
        if await self.is_fullscreen_video():
            await self._kodi.call_method("Input.ShowOSD")
        else:
            await self._kodi.call_method("Input.ContextMenu")

    @retry()
    async def home(self):
        """Send Home command."""
        await self._kodi.call_method("Input.Home")

    async def power_on(self):
        """Handle connection to Kodi device."""
        self.event_loop.create_task(self.connect())
        await asyncio.sleep(0)
        return ucapi.StatusCodes.OK

    @retry()
    async def power_off(self):
        """Send Power Off command."""
        try:
            await self._kodi.call_method("Application.Quit")
        except TransportError as ex:
            _LOG.info("[%s] Power off : client is already disconnected %s", self.device_config.address, ex)
            try:
                await self.event_loop.create_task(self._update_states())
            # pylint: disable = W0718
            except Exception:
                pass

    @retry()
    async def command_button(self, button: ButtonKeymap):
        """Call a button command."""
        await self._kodi.call_method(
            "Input.ButtonEvent",
            **{"button": button["button"], "keymap": button.get("keymap", "KB"), "holdtime": button.get("holdtime", 0)},
        )

    @retry()
    async def command_action(self, command: str):
        """Send custom command see https://kodi.wiki/view/Keymap."""
        await self._kodi.call_method("Input.ExecuteAction", **{"action": command})

    @retry()
    async def call_command(self, command: str, **kwargs):
        """Send custom command."""
        await self._kodi.call_method(command, **kwargs)

    @retry()
    async def call_command_args(self, command: str, *args):
        """Send custom command."""
        await self._kodi.call_method_args(command, *args)

    @retry()
    async def seek(self, media_position: int):
        """Seek to given position in seconds."""
        if self._no_active_players or media_position is None:
            return
        m, s = divmod(media_position, 60)
        h, m = divmod(m, 60)
        await self._kodi.call_method(
            "Player.Seek",
            **{
                "playerid": self.player_id,
                "value": {"time": {"hours": h, "minutes": m, "seconds": s, "milliseconds": 0}},
            },
        )

    @retry()
    async def select_chapter(self, chapter_name: str):
        """Skip to given chapter name."""
        if self._no_active_players or self._chapters is None:
            return
        for chapter in self._chapters:
            if chapter.get("name", "") == chapter_name:
                position: int = chapter.get("time", 0)
                _LOG.debug("[%s] Skipping to chapter %s (%s)", self.device_config.address, chapter_name, position)
                await self.seek(position)
                return
        _LOG.warning("[%s] Skipping to chapter %s : not found", self.device_config.address, chapter_name)

    @retry()
    async def select_audio_track(self, track_name: str):
        """Skip to given audio track name."""
        if self._no_active_players:
            return
        for track in self.audio_tracks:
            if (
                track.get_track_name(KodiStreamConfig(self._device_config.sensor_audio_stream_config)) == track_name
                or track.get_track_name(KodiStreamConfig(self._device_config.sensor_audio_stream_config)) == track_name
            ):
                _LOG.debug("[%s] Switch audio track to %s (%s)", self.device_config.address, track_name, track.index)
                await self._kodi.set_audio_stream(track.index)
                return
        _LOG.warning("[%s] Switch audio track to %s : not found", self.device_config.address, track_name)

    @retry()
    async def select_subtitle_track(self, track_name: str):
        """Skip to given subtitle track name."""
        if self._no_active_players:
            return
        for track in self.subtitle_tracks:
            if (
                track.get_track_name(KodiStreamConfig(self._device_config.sensor_subtitle_stream_config)) == track_name
                or track.get_track_name(KodiStreamConfig(self._device_config.sensor_subtitle_stream_config))
                == track_name
            ):
                if not track.enabled:
                    _LOG.debug("[%s] Disable subtitles", self.device_config.address)
                    await self.command_action("showsubtitles")
                    # await self._kodi.set_subtitle_stream(self.current_subtitle_track.index, False)
                else:
                    _LOG.debug(
                        "[%s] Switch subtitle track to %s (%s)", self.device_config.address, track_name, track.index
                    )
                    await self._kodi.set_subtitle_stream(track.index)
                return
        _LOG.warning("[%s] Switch subtitle track to %s : not found", self.device_config.address, track_name)

    @retry()
    async def zoom(self, mode: Literal["in", "out"] | int):
        """Zoom in/out or to a given level 1-10."""
        if self._no_active_players:
            return
        arguments = {"playerid": self.player_id, "zoom": mode}
        _LOG.debug("[%s] Set zoom Player.Zoom %s", self.device_config.address, arguments)
        await self._kodi.call_method("Player.Zoom", **arguments)

    @retry()
    async def view_mode(self, mode: str):
        """Set view mode.

        :param mode: normal,zoom,stretch4x3,widezoom,stretch16x9,original,stretch16x9nonlin, zoom120width,zoom110width
        """
        arguments = {"viewmode": mode}
        _LOG.debug("[%s] View modePlayer.SetViewMode %s", self.device_config.address, arguments)
        await self._kodi.call_method("Player.SetViewMode", **arguments)

    @retry()
    async def speed(self, value: Literal["increment", "decrement"] | int):
        """Set playback speed.

        :param value: Speed int value to set or "increment","decrement" values
        """
        if self._no_active_players:
            return
        arguments = {"playerid": self.player_id, "speed": value}
        _LOG.debug("[%s] Set speed Player.SetSpeed %s", self.device_config.address, arguments)
        await self._kodi.call_method("Player.SetSpeed", **arguments)

    @retry()
    async def audio_delay(self, offset: float):
        """Set audio delay relatively.

        :param offset: Offset delay in seconds.
        """
        if self._no_active_players:
            return
        current_delay = await self._kodi.call_method("Player.GetAudioDelay")
        try:
            current_delay = float(current_delay.get("offset", 0))
        except ValueError:
            pass
        arguments = {"playerid": self.player_id, "offset": offset + current_delay}
        _LOG.debug("[%s] Set audio delay Player.SetAudioDelay %s", self.device_config.address, arguments)
        await self._kodi.call_method("Player.SetAudioDelay", **arguments)

    async def get_chapters(self) -> dict[str, Any]:
        """Return chapters of running video."""
        _LOG.debug("[%s] Extract video chapters", self.device_config.address)
        return await self._kodi.get_player_chapters(self._players[0])

    async def get_app_language(self) -> str | None:
        """Return current app language."""
        try:
            language = (await self._kodi.get_application_properties(["language"]))["language"]
            _LOG.debug("[%s] Kodi language : %s", self.device_config.address, language)
            return language
        # pylint: disable = W0718
        except Exception:
            return None

    async def get_name(self) -> str | None:
        """Return Kodi instance name."""
        return await self._kodi.get_name()

    async def is_fullscreen_video(self) -> bool:
        """Check if Kodi is in fullscreen (playing video)."""
        if self.state in (MediaStates.OFF, MediaStates.ON, MediaStates.UNKNOWN):
            return False
        try:
            result = await self._kodi.call_method("Gui.GetProperties", **{"properties": ["fullscreen"]})
            if result["fullscreen"] and result["fullscreen"] is True:
                return True
        # pylint: disable = W0718
        except Exception as ex:
            _LOG.debug("[%s] Couldn't retrieve Kodi's window state %s", self.device_config.address, ex)
        return False
