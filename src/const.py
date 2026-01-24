"""
Constants used for Kodi integration.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

from enum import Enum
from typing import Any, TypedDict

from ucapi.media_player import Commands, Features, MediaType
from ucapi.ui import Buttons, DeviceButtonMapping, UiPage


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
    SENSOR_VOLUME = "sensor_volume"
    SENSOR_VOLUME_MUTED = "sensor_volume_muted"


class KodiSensorStreamConfig(int, Enum):
    """Stream sensor configuration."""

    STREAM_NAME = 1
    LANGUAGE_NAME = 2
    FULL = 3


KODI_SENSOR_STREAM_CONFIG_LABELS = [
    {"id": f"{KodiSensorStreamConfig.STREAM_NAME}", "label": {"en": "Stream name", "fr": "Nom du flux"}},
    {"id": f"{KodiSensorStreamConfig.LANGUAGE_NAME}", "label": {"en": "Language name", "fr": "Nom de la langue"}},
    {
        "id": f"{KodiSensorStreamConfig.FULL}",
        "label": {"en": "Language and stream names", "fr": "Langue et nom du flux"},
    },
]

KODI_DEFAULT_NAME = "Kodi"

KODI_MEDIA_TYPES = {
    "music": MediaType.MUSIC,
    "artist": MediaType.MUSIC,
    "album": MediaType.MUSIC,
    "song": MediaType.MUSIC,
    "video": MediaType.VIDEO,
    "set": MediaType.MUSIC,
    "musicvideo": MediaType.VIDEO,
    "movie": MediaType.MOVIE,
    "tvshow": MediaType.TVSHOW,
    "season": MediaType.TVSHOW,
    "episode": MediaType.TVSHOW,
    # Type 'channel' is used for radio or tv streams from pvr
    "channel": MediaType.TVSHOW,
    # Type 'audio' is used for audio media, that Kodi couldn't scroblle
    "audio": MediaType.MUSIC,
}

KODI_ARTWORK_LABELS = [
    {"id": "thumb", "label": {"en": "Thumbnail", "fr": "Standard"}},
    {"id": "fanart", "label": {"en": "Fan art", "fr": "Fan art"}},
    {"id": "poster", "label": {"en": "Poster", "fr": "Poster"}},
    {"id": "landscape", "label": {"en": "Landscape", "fr": "Paysage"}},
    {"id": "keyart", "label": {"en": "Key art", "fr": "Key art"}},
    {"id": "banner", "label": {"en": "Banner", "fr": "Affiche"}},
    {"id": "clearart", "label": {"en": "Clear art", "fr": "Clear art"}},
    {"id": "clearlogo", "label": {"en": "Clear logo", "fr": "Clear logo"}},
    {"id": "discart", "label": {"en": "Disc art", "fr": "Disc art"}},
    {"id": "icon", "label": {"en": "Icon", "fr": "Icône"}},
    {"id": "set.fanart", "label": {"en": "Fanart set", "fr": "Jeu de fanart"}},
    {"id": "set.poster", "label": {"en": "Poster set", "fr": "Jeu de poster"}},
]

KODI_ARTWORK_TVSHOWS_LABELS = [
    {"id": "thumb", "label": {"en": "Thumbnail", "fr": "Standard"}},
    {"id": "season.banner", "label": {"en": "Season banner", "fr": "Affiche de la saison"}},
    {"id": "season.landscape", "label": {"en": "Season landscape", "fr": "Saison en paysage"}},
    {"id": "season.poster", "label": {"en": "Season poster", "fr": "Affiche de la saison"}},
    {"id": "tvshow.banner", "label": {"en": "TV show banner", "fr": "Affiche de la série"}},
    {"id": "tvshow.characterart", "label": {"en": "TV show character art", "fr": "Personnages de la série"}},
    {"id": "tvshow.clearart", "label": {"en": "TV show clear art", "fr": "Affiche sans fond de la série"}},
    {"id": "tvshow.clearlogo", "label": {"en": "TV show clear logo", "fr": "Logo sans fond de la série"}},
    {"id": "tvshow.fanart", "label": {"en": "TV show fan art", "fr": "Fan art de la série"}},
    {"id": "tvshow.landscape", "label": {"en": "TV show landscape", "fr": "Affiche en paysage"}},
    {"id": "tvshow.poster", "label": {"en": "TV show poster", "fr": "Affiche de la série"}},
    {"id": "icon", "label": {"en": "Icon", "fr": "Icône"}},
]

KODI_DEFAULT_ARTWORK = "thumb"
KODI_DEFAULT_TVSHOW_ARTWORK = "tvshow.poster"

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
]

# Taken from https://kodi.wiki/view/JSON-RPC_API/v10#Input.Action
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

# Taken from https://kodi.wiki/view/JSON-RPC_API/v10#Input.Action
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
