"""
Constants used for Kodi integration.

:copyright: (c) 2026 by Albaintor
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Type, TypedDict

from ucapi.media_player import Commands, Features, MediaContentType
from ucapi.ui import Buttons, DeviceButtonMapping, UiPage


@dataclass
class PlaylistInfo:
    """Playlist info."""

    playlist_id: int
    position: int
    playlist: dict[str, Any]


@dataclass
class PaginationOptions:
    """
    Pagination metadata returned by the client.

    Attributes:
        page (int):
            Current page number, 1-based. Must correspond to the requested page.
        limit (int):
            Number of items returned in this page.
        count (int|None):
            Optional if known: Total number of available items across all pages.
    """

    page: int
    limit: int
    count: int | None = None


class IKodiDevice:
    """Kodi client interface."""

    @property
    def client(self):
        """Return Kodi client."""
        raise NotImplementedError()

    @property
    def server(self):
        """Return Kodi server."""
        raise NotImplementedError()

    @property
    def device_config(self):
        """Return device configuration."""
        raise NotImplementedError()

    @property
    def app_language_code(self) -> str:
        """App language code."""
        raise NotImplementedError()

    async def get_current_playlist(self) -> PlaylistInfo | None:
        """Return current position in playlist and current playlist."""
        raise NotImplementedError()


class ButtonKeymap(TypedDict):
    """Kodi keymap."""

    button: str
    keymap: str | None
    holdtime: int | None


class MethodCall(TypedDict):
    """Kodi method call."""

    method: str
    params: dict[str, Any]


class KodiSensors(str, Enum):
    """Kodi sensor values."""

    SENSOR_AUDIO_STREAM = "sensor_audio_stream"
    SENSOR_SUBTITLE_STREAM = "sensor_subtitle_stream"
    SENSOR_CHAPTER = "sensor_chapter"
    SENSOR_VIDEO_INFO = "sensor_video_info"
    SENSOR_AUDIO_INFO = "sensor_audio_info"
    SENSOR_VOLUME = "sensor_volume"
    SENSOR_VOLUME_MUTED = "sensor_volume_muted"


class KodiSelects(str, Enum):
    """Kodi select values."""

    SELECT_AUDIO_STREAM = "select_audio_stream"
    SELECT_SUBTITLE_STREAM = "select_subtitle_stream"
    SELECT_CHAPTER = "select_chapter"


class KodiStreamConfig(int, Enum):
    """Stream display configuration."""

    STREAM_NAME = 1
    LANGUAGE_NAME = 2
    FULL = 3


class KodiMediaTypes(str, Enum):
    """Kodi media types."""

    VIDEOS = "video"
    MUSIC = "music"
    PICTURES = "pictures"
    FILES = "files"
    PROGRAMS = "programs"


class KodiObjectType(int, Enum):
    """Kodi JSON RPC object types."""

    EMPTY = 0
    MOVIE = 1
    GENRE = 2
    TV_SHOW = 3
    SEASON = 4
    EPISODE = 5
    FILE = 6
    ALBUM = 7
    ARTIST = 8
    SONG = 9
    PLAYLIST = 10


KODI_POWEROFF_COMMANDS: dict[str, dict[str, str]] = {
    "Application.Quit": {"en": "Quit application", "fr": "Quitter l'application"},
    "System.Shutdown": {"en": "Shutdown", "fr": "Eteindre"},
    "System.Hibernate": {"en": "Hibernate", "fr": "Veille prolongée"},
    "System.Suspend": {"en": "Suspend", "fr": "Veille"},
    "System.Reboot": {"en": "Reboot", "fr": "Redémarrer"},
}

KODI_SENSOR_STREAM_CONFIG_LABELS = [
    {"id": f"{int(KodiStreamConfig.STREAM_NAME)}", "label": {"en": "Stream name", "fr": "Nom du flux"}},
    {"id": f"{int(KodiStreamConfig.LANGUAGE_NAME)}", "label": {"en": "Language name", "fr": "Nom de la langue"}},
    {
        "id": f"{int(KodiStreamConfig.FULL)}",
        "label": {"en": "Language and stream names", "fr": "Langue et nom du flux"},
    },
]

KODI_DEFAULT_NAME = "Kodi"


KODI_MEDIA_TYPES: dict[str, MediaContentType] = {
    "music": MediaContentType.MUSIC,
    "artist": MediaContentType.ARTIST,
    "album": MediaContentType.ALBUM,
    "song": MediaContentType.TRACK,
    "video": MediaContentType.VIDEO,
    "set": MediaContentType.MUSIC,
    "musicvideo": MediaContentType.VIDEO,
    "movie": MediaContentType.MOVIE,
    "tvshow": MediaContentType.TV_SHOW,
    "season": MediaContentType.SEASON,
    "episode": MediaContentType.EPISODE,
    # Type 'channel' is used for radio or tv streams from pvr
    "channel": MediaContentType.CHANNEL,
    # Type 'audio' is used for audio media, that Kodi couldn't scroblle
    "audio": MediaContentType.MUSIC,
}

KODI_FEATURES = [
    Features.ON_OFF,
    #  Features.TOGGLE,
    Features.VOLUME,
    Features.VOLUME_UP_DOWN,
    Features.MUTE_TOGGLE,
    Features.MUTE,
    Features.UNMUTE,
    Features.PLAY_PAUSE,
    Features.STOP,
    Features.NEXT,
    Features.PREVIOUS,
    Features.FAST_FORWARD,
    Features.REWIND,
    Features.MEDIA_TITLE,
    Features.MEDIA_IMAGE_URL,
    Features.MEDIA_TYPE,
    Features.MEDIA_DURATION,
    Features.MEDIA_POSITION,
    Features.DPAD,
    Features.NUMPAD,
    Features.HOME,
    Features.MENU,
    Features.CONTEXT_MENU,
    Features.GUIDE,
    Features.INFO,
    Features.COLOR_BUTTONS,
    Features.CHANNEL_SWITCHER,
    Features.SELECT_SOURCE,
    Features.SELECT_SOUND_MODE,
    Features.AUDIO_TRACK,
    Features.SUBTITLE,
    Features.RECORD,
    Features.SEEK,
    Features.SETTINGS,
    Features.SHUFFLE,
    Features.REPEAT,
    Features.PLAY_PAUSE,
    Features.PLAY_MEDIA,
    Features.PLAY_MEDIA_ACTION,
    Features.CLEAR_PLAYLIST,
    Features.BROWSE_MEDIA,
    Features.SEARCH_MEDIA,
    Features.SEARCH_MEDIA_CLASSES,
]

# Taken from https://kodi.wiki/view/JSON-RPC_API/v13#Input.Action
KODI_SIMPLE_COMMANDS = {
    "MENU_VIDEO": "showvideomenu",  # TODO : showvideomenu not working ?
    "MODE_FULLSCREEN": "togglefullscreen",
    "MODE_ZOOM_IN": "zoomin",
    "MODE_ZOOM_OUT": "zoomout",
    "MODE_INCREASE_PAR": "increasepar",
    "MODE_DECREASE_PAR": "decreasepar",
    "MODE_SHOW_SUBTITLES": "showsubtitles",
    "MODE_SUBTITLES_DELAY_MINUS": "subtitledelayminus",
    "MODE_SUBTITLES_DELAY_PLUS": "subtitledelayplus",
    "MODE_AUDIO_DELAY_MINUS": "audiodelayminus",
    "MODE_AUDIO_DELAY_PLUS": "audiodelayplus",
    "MODE_DELETE": "delete",
    "APP_SHUTDOWN": "System.Shutdown",
    "APP_REBOOT": "System.Reboot",
    "APP_HIBERNATE": "System.Hibernate",
    "APP_SUSPEND": "System.Suspend",
    "ACTION_BLUE": "blue",
    "ACTION_GREEN": "green",
    "ACTION_RED": "red",
    "ACTION_YELLOW": "yellow",
}

KODI_SIMPLE_COMMANDS_DIRECT = ["System.Hibernate", "System.Reboot", "System.Shutdown", "System.Suspend"]

# Taken from https://kodi.wiki/view/JSON-RPC_API/v13#Input.Action
# (expand schema description),
# more info also on https://forum.kodi.tv/showthread.php?tid=349151 which explains the logic
KODI_ACTIONS_KEYMAP = {
    Commands.SUBTITLE: "nextsubtitle",
    Commands.AUDIO_TRACK: "audionextlanguage",
    Commands.FAST_FORWARD: "fastforward",
    Commands.REWIND: "rewind",
    Commands.MENU: "menu",
    Commands.INFO: "info",
}


# Taken from https://kodi.wiki/view/List_of_keynames,
# For remote buttons :
# see https://github.com/xbmc/xbmc/blob/master/system/keymaps/remote.xml for R1 keymap or
# see https://github.com/xbmc/xbmc/blob/master/system/keymaps/keyboard.xml for KB keymap
KODI_BUTTONS_KEYMAP: dict[str, ButtonKeymap | MethodCall] = {
    Commands.CHANNEL_UP: ButtonKeymap(**{"button": "pageplus", "keymap": "R1"}),  # channelup or pageup
    Commands.CHANNEL_DOWN: ButtonKeymap(**{"button": "pageminus", "keymap": "R1"}),  # channeldown or pagedown
    Commands.CURSOR_UP: ButtonKeymap(**{"button": "up", "keymap": "R1"}),
    Commands.CURSOR_DOWN: ButtonKeymap(**{"button": "down", "keymap": "R1"}),
    Commands.CURSOR_LEFT: ButtonKeymap(**{"button": "left", "keymap": "R1"}),
    Commands.CURSOR_RIGHT: ButtonKeymap(**{"button": "right", "keymap": "R1"}),
    Commands.CURSOR_ENTER: ButtonKeymap(**{"button": "enter"}),
    Commands.BACK: ButtonKeymap(**{"button": "backspace"}),
    # Send numbers through "R1" keymap so they can be used for character input (like on old phones)
    Commands.DIGIT_0: ButtonKeymap(**{"button": "zero", "keymap": "R1"}),
    Commands.DIGIT_1: ButtonKeymap(**{"button": "one", "keymap": "R1"}),
    Commands.DIGIT_2: ButtonKeymap(**{"button": "two", "keymap": "R1"}),
    Commands.DIGIT_3: ButtonKeymap(**{"button": "three", "keymap": "R1"}),
    Commands.DIGIT_4: ButtonKeymap(**{"button": "four", "keymap": "R1"}),
    Commands.DIGIT_5: ButtonKeymap(**{"button": "five", "keymap": "R1"}),
    Commands.DIGIT_6: ButtonKeymap(**{"button": "six", "keymap": "R1"}),
    Commands.DIGIT_7: ButtonKeymap(**{"button": "seven", "keymap": "R1"}),
    Commands.DIGIT_8: ButtonKeymap(**{"button": "eight", "keymap": "R1"}),
    Commands.DIGIT_9: ButtonKeymap(**{"button": "nine", "keymap": "R1"}),
    Commands.RECORD: ButtonKeymap(**{"button": "record", "keymap": "R1"}),
    Commands.GUIDE: ButtonKeymap(**{"button": "guide", "keymap": "R1"}),
    Commands.FUNCTION_GREEN: ButtonKeymap(**{"button": "green", "keymap": "R1"}),
    Commands.FUNCTION_BLUE: ButtonKeymap(**{"button": "blue", "keymap": "R1"}),
    Commands.FUNCTION_RED: ButtonKeymap(**{"button": "red", "keymap": "R1"}),
    Commands.FUNCTION_YELLOW: ButtonKeymap(**{"button": "yellow", "keymap": "R1"}),
    Commands.SETTINGS: MethodCall(method="GUI.ActivateWindow", params={"window": "settings"}),
    # Commands.STOP: ButtonKeymap(**{"button": "stop", "keymap": "R1"}),
}

KODI_ADVANCED_SIMPLE_COMMANDS: dict[str, MethodCall | str] = {
    "MODE_TOGGLE_GUI": {"method": "GUI.SetFullscreen", "params": {"fullscreen": "toggle"}, "holdtime": None},
    "MODE_SHOW_SUBTITLES_STREAM": "dialogselectsubtitle",
    "MODE_SHOW_AUDIO_STREAM": "dialogselectaudio",
    "MODE_SHOW_SUBTITLES_MENU": {
        "method": "GUI.ActivateWindow",
        "params": {"window": "osdsubtitlesettings"},
        "holdtime": None,
    },
    "MODE_SHOW_AUDIO_MENU": {
        "method": "GUI.ActivateWindow",
        "params": {"window": "osdaudiosettings"},
        "holdtime": None,
    },
    "MODE_SHOW_VIDEO_MENU": {
        "method": "GUI.ActivateWindow",
        "params": {"window": "osdvideosettings"},
        "holdtime": None,
    },
    "MODE_SHOW_BOOKMARKS_MENU": {
        "method": "GUI.ActivateWindow",
        "params": {"window": "videobookmarks"},
        "holdtime": None,
    },
    "MODE_SHOW_SUBTITLE_SEARCH_MENU": {
        "method": "GUI.ActivateWindow",
        "params": {"window": "subtitlesearch"},
        "holdtime": None,
    },
    "MODE_SCREENSAVER": {"method": "GUI.ActivateWindow", "params": {"window": "screensaver"}},
}

KODI_ALTERNATIVE_BUTTONS_KEYMAP: dict[str, MethodCall] = {
    Commands.CHANNEL_UP: {
        "method": "Input.ExecuteAction",
        "params": {"action": "pageup"},
    },  # channelup or pageup
    Commands.CHANNEL_DOWN: {
        "method": "Input.ExecuteAction",
        "params": {"action": "pagedown"},
    },  # channeldown or pagedown
    Commands.CURSOR_UP: {"method": "Input.Up", "params": {}},
    Commands.CURSOR_DOWN: {"method": "Input.Down", "params": {}},
    Commands.CURSOR_LEFT: {"method": "Input.Left", "params": {}},
    Commands.CURSOR_RIGHT: {"method": "Input.Right", "params": {}},
    Commands.CURSOR_ENTER: {"method": "Input.Select", "params": {}},
    Commands.BACK: {"method": "Input.Back", "params": {}},
}

KODI_REMOTE_BUTTONS_MAPPING: list[DeviceButtonMapping] = [
    DeviceButtonMapping(**{"button": Buttons.BACK, "short_press": {"cmd_id": Commands.BACK}}),
    DeviceButtonMapping(**{"button": Buttons.HOME, "short_press": {"cmd_id": Commands.HOME}}),
    DeviceButtonMapping(**{"button": Buttons.CHANNEL_DOWN, "short_press": {"cmd_id": Commands.CHANNEL_DOWN}}),
    DeviceButtonMapping(**{"button": Buttons.CHANNEL_UP, "short_press": {"cmd_id": Commands.CHANNEL_UP}}),
    DeviceButtonMapping(**{"button": Buttons.DPAD_UP, "short_press": {"cmd_id": Commands.CURSOR_UP}}),
    DeviceButtonMapping(**{"button": Buttons.DPAD_DOWN, "short_press": {"cmd_id": Commands.CURSOR_DOWN}}),
    DeviceButtonMapping(**{"button": Buttons.DPAD_LEFT, "short_press": {"cmd_id": Commands.CURSOR_LEFT}}),
    DeviceButtonMapping(**{"button": Buttons.DPAD_RIGHT, "short_press": {"cmd_id": Commands.CURSOR_RIGHT}}),
    DeviceButtonMapping(**{"button": Buttons.DPAD_MIDDLE, "short_press": {"cmd_id": Commands.CURSOR_ENTER}}),
    DeviceButtonMapping(**{"button": Buttons.PLAY, "short_press": {"cmd_id": Commands.PLAY_PAUSE}}),
    DeviceButtonMapping(**{"button": Buttons.PREV, "short_press": {"cmd_id": Commands.PREVIOUS}}),
    DeviceButtonMapping(**{"button": Buttons.NEXT, "short_press": {"cmd_id": Commands.NEXT}}),
    DeviceButtonMapping(**{"button": Buttons.VOLUME_UP, "short_press": {"cmd_id": Commands.VOLUME_UP}}),
    DeviceButtonMapping(**{"button": Buttons.VOLUME_DOWN, "short_press": {"cmd_id": Commands.VOLUME_DOWN}}),
    DeviceButtonMapping(**{"button": Buttons.MUTE, "short_press": {"cmd_id": Commands.MUTE_TOGGLE}}),
    DeviceButtonMapping(**{"button": Buttons.STOP, "short_press": {"cmd_id": Commands.STOP}}),
    DeviceButtonMapping(**{"button": Buttons.MENU, "short_press": {"cmd_id": Commands.CONTEXT_MENU}}),
]

# All defined commands for remote entity
# TODO rename simple commands to be compliant to expected names in R2
KODI_REMOTE_SIMPLE_COMMANDS = [
    *list(KODI_SIMPLE_COMMANDS.keys()),
    *list(KODI_ADVANCED_SIMPLE_COMMANDS.keys()),
    *list(KODI_ACTIONS_KEYMAP.keys()),
    *list(KODI_BUTTONS_KEYMAP.keys()),
    Commands.CONTEXT_MENU,
    Commands.VOLUME_UP,
    Commands.VOLUME_DOWN,
    Commands.MUTE_TOGGLE,
    Commands.MUTE,
    Commands.UNMUTE,
    Commands.PLAY_PAUSE,
    Commands.STOP,
    Commands.HOME,
]

KODI_REMOTE_UI_PAGES: list[UiPage] = [
    UiPage(
        **{
            "page_id": "Kodi commands",
            "name": "Kodi commands",
            "grid": {"width": 4, "height": 6},
            "items": [
                {
                    "command": {"cmd_id": "remote.send", "params": {"command": Commands.INFO, "repeat": 1}},
                    "icon": "uc:info",
                    "location": {"x": 0, "y": 0},
                    "type": "icon",
                },
                {
                    "command": {"cmd_id": "remote.send", "params": {"command": Commands.AUDIO_TRACK, "repeat": 1}},
                    "icon": "uc:language",
                    "location": {"x": 1, "y": 0},
                    "type": "icon",
                },
                {
                    "command": {"cmd_id": "remote.send", "params": {"command": Commands.SUBTITLE, "repeat": 1}},
                    "icon": "uc:cc",
                    "location": {"x": 2, "y": 0},
                    "type": "icon",
                },
                {
                    "command": {"cmd_id": "MODE_SHOW_SUBTITLES"},
                    "text": "Toggle subtitles",
                    "location": {"x": 3, "y": 0},
                    "type": "text",
                },
                {
                    "command": {"cmd_id": "MODE_FULLSCREEN"},
                    "text": "Full screen",
                    "location": {"x": 0, "y": 1},
                    "type": "text",
                },
                {
                    "command": {"cmd_id": "MODE_ZOOM_IN"},
                    "text": "Zoom in",
                    "location": {"x": 1, "y": 1},
                    "type": "text",
                },
                {
                    "command": {"cmd_id": "MODE_ZOOM_OUT"},
                    "text": "Zoom out",
                    "location": {"x": 2, "y": 1},
                    "type": "text",
                },
                {
                    "command": {"cmd_id": Commands.CONTEXT_MENU},
                    "icon": "uc:menu",
                    "location": {"x": 3, "y": 5},
                    "type": "icon",
                },
            ],
        }
    ),
    UiPage(
        **{
            "page_id": "Kodi numbers",
            "name": "Kodi numbers",
            "grid": {"height": 4, "width": 3},
            "items": [
                {
                    "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_1, "repeat": 1}},
                    "location": {"x": 0, "y": 0},
                    "text": "1",
                    "type": "text",
                },
                {
                    "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_2, "repeat": 1}},
                    "location": {"x": 1, "y": 0},
                    "text": "2",
                    "type": "text",
                },
                {
                    "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_3, "repeat": 1}},
                    "location": {"x": 2, "y": 0},
                    "text": "3",
                    "type": "text",
                },
                {
                    "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_4, "repeat": 1}},
                    "location": {"x": 0, "y": 1},
                    "text": "4",
                    "type": "text",
                },
                {
                    "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_5, "repeat": 1}},
                    "location": {"x": 1, "y": 1},
                    "text": "5",
                    "type": "text",
                },
                {
                    "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_6, "repeat": 1}},
                    "location": {"x": 2, "y": 1},
                    "text": "6",
                    "type": "text",
                },
                {
                    "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_7, "repeat": 1}},
                    "location": {"x": 0, "y": 2},
                    "text": "7",
                    "type": "text",
                },
                {
                    "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_8, "repeat": 1}},
                    "location": {"x": 1, "y": 2},
                    "text": "8",
                    "type": "text",
                },
                {
                    "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_9, "repeat": 1}},
                    "location": {"x": 2, "y": 2},
                    "text": "9",
                    "type": "text",
                },
                {
                    "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_0, "repeat": 1}},
                    "location": {"x": 1, "y": 3},
                    "text": "0",
                    "type": "text",
                },
            ],
        }
    ),
]


def filter_attributes(attributes, attribute_type: Type[Enum]) -> dict[str, Any]:
    """Filter attributes based on an Enum class."""
    valid_keys = {e.value for e in attribute_type}
    return {k: v for k, v in attributes.items() if k in valid_keys}


def key_update_helper(input_attributes, key: str, value: str | None, attributes):
    """Return modified attributes only."""
    if value is None:
        return attributes

    if key in input_attributes:
        if input_attributes[key] != value:
            attributes[key] = value
    else:
        attributes[key] = value

    return attributes
