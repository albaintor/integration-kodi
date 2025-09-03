"""
Constants used for Kodi integration.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

from typing import TypedDict

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
    params: dict[str, any]
    holdtime: int | None


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
    # Features.SELECT_SOURCE,
    Features.AUDIO_TRACK,
    Features.SUBTITLE,
    Features.RECORD,
    Features.SEEK,
    # Features.SETTINGS
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
KODI_BUTTONS_KEYMAP: dict[str, ButtonKeymap] = {
    Commands.CHANNEL_UP: {"button": "pageplus", "keymap": "R1"},  # channelup or pageup
    Commands.CHANNEL_DOWN: {"button": "pageminus", "keymap": "R1"},  # channeldown or pagedown
    Commands.CURSOR_UP: {"button": "up", "keymap": "R1"},
    Commands.CURSOR_DOWN: {"button": "down", "keymap": "R1"},
    Commands.CURSOR_LEFT: {"button": "left", "keymap": "R1"},
    Commands.CURSOR_RIGHT: {"button": "right", "keymap": "R1"},
    Commands.CURSOR_ENTER: {"button": "enter"},
    Commands.BACK: {"button": "backspace"},
    # Send numbers through "R1" keymap so they can be used for character input (like on old phones)
    Commands.DIGIT_0: {"button": "zero", "keymap": "R1"},
    Commands.DIGIT_1: {"button": "one", "keymap": "R1"},
    Commands.DIGIT_2: {"button": "two", "keymap": "R1"},
    Commands.DIGIT_3: {"button": "three", "keymap": "R1"},
    Commands.DIGIT_4: {"button": "four", "keymap": "R1"},
    Commands.DIGIT_5: {"button": "five", "keymap": "R1"},
    Commands.DIGIT_6: {"button": "six", "keymap": "R1"},
    Commands.DIGIT_7: {"button": "seven", "keymap": "R1"},
    Commands.DIGIT_8: {"button": "eight", "keymap": "R1"},
    Commands.DIGIT_9: {"button": "nine", "keymap": "R1"},
    Commands.RECORD: {"button": "record", "keymap": "R1"},
    Commands.GUIDE: {"button": "guide", "keymap": "R1"},
    Commands.FUNCTION_GREEN: {"button": "green", "keymap": "R1"},
    Commands.FUNCTION_BLUE: {"button": "blue", "keymap": "R1"},
    Commands.FUNCTION_RED: {"button": "red", "keymap": "R1"},
    Commands.FUNCTION_YELLOW: {"button": "yellow", "keymap": "R1"},
}

KODI_ALTERNATIVE_BUTTONS_KEYMAP: dict[str, MethodCall] = {
    Commands.CHANNEL_UP: {"method": "Input.ExecuteAction", "params": {"action": "pageup"}, "holdtime": None},  # channelup or pageup
    Commands.CHANNEL_DOWN: {"method": "Input.ExecuteAction", "params": {"action": "pagedown"}, "holdtime": None},  # channeldown or pagedown
    Commands.CURSOR_UP: {"method": "Input.Up", "params": {}, "holdtime": None},
    Commands.CURSOR_DOWN: {"method": "Input.Down", "params": {}, "holdtime": None},
    Commands.CURSOR_LEFT: {"method": "Input.Left", "params": {}, "holdtime": None},
    Commands.CURSOR_RIGHT: {"method": "Input.Right", "params": {}, "holdtime": None},
    Commands.CURSOR_ENTER: {"method": "Input.Select", "params": {}, "holdtime": None},
    Commands.BACK: {"method": "Input.Back", "params": {}, "holdtime": None},
    # Commands.DIGIT_0: {"method": "Input.zero"},
    # Commands.DIGIT_1: {"method": "Input.one"},
    # Commands.DIGIT_2: {"method": "Input.two"},
    # Commands.DIGIT_3: {"method": "Input.three"},
    # Commands.DIGIT_4: {"method": "Input.four"},
    # Commands.DIGIT_5: {"method": "Input.five"},
    # Commands.DIGIT_6: {"method": "Input.six"},
    # Commands.DIGIT_7: {"method": "Input.seven"},
    # Commands.DIGIT_8: {"method": "Input.eight"},
    # Commands.DIGIT_9: {"method": "Input.nine"},
    # Commands.RECORD: {"method": "Input.record"},
    # Commands.GUIDE: {"method": "Input.guide"},
    # Commands.FUNCTION_GREEN: {"method": "Input.green"},
    # Commands.FUNCTION_BLUE: {"method": "Input.blue"},
    # Commands.FUNCTION_RED: {"method": "Input.red"},
    # Commands.FUNCTION_YELLOW: {"method": "Input.yellow"},
}

KODI_REMOTE_BUTTONS_MAPPING: [DeviceButtonMapping] = [
    {"button": Buttons.BACK, "short_press": {"cmd_id": Commands.BACK}},
    {"button": Buttons.HOME, "short_press": {"cmd_id": Commands.HOME}},
    {"button": Buttons.CHANNEL_DOWN, "short_press": {"cmd_id": Commands.CHANNEL_DOWN}},
    {"button": Buttons.CHANNEL_UP, "short_press": {"cmd_id": Commands.CHANNEL_UP}},
    {"button": Buttons.DPAD_UP, "short_press": {"cmd_id": Commands.CURSOR_UP}},
    {"button": Buttons.DPAD_DOWN, "short_press": {"cmd_id": Commands.CURSOR_DOWN}},
    {"button": Buttons.DPAD_LEFT, "short_press": {"cmd_id": Commands.CURSOR_LEFT}},
    {"button": Buttons.DPAD_RIGHT, "short_press": {"cmd_id": Commands.CURSOR_RIGHT}},
    {"button": Buttons.DPAD_MIDDLE, "short_press": {"cmd_id": Commands.CURSOR_ENTER}},
    {"button": Buttons.PLAY, "short_press": {"cmd_id": Commands.PLAY_PAUSE}},
    {"button": Buttons.PREV, "short_press": {"cmd_id": Commands.PREVIOUS}},
    {"button": Buttons.NEXT, "short_press": {"cmd_id": Commands.NEXT}},
    {"button": Buttons.VOLUME_UP, "short_press": {"cmd_id": Commands.VOLUME_UP}},
    {"button": Buttons.VOLUME_DOWN, "short_press": {"cmd_id": Commands.VOLUME_DOWN}},
    {"button": Buttons.MUTE, "short_press": {"cmd_id": Commands.MUTE_TOGGLE}},
    {"button": "STOP", "short_press": {"cmd_id": Commands.STOP}},  # TODO missing R3 buttons in UCAPI
    {"button": "MENU", "short_press": {"cmd_id": Commands.CONTEXT_MENU}},  # TODO missing R3 buttons in UCAPI
]

# All defined commands for remote entity
# TODO rename simple commands to be compliant to expected names in R2
KODI_REMOTE_SIMPLE_COMMANDS = [
    *list(KODI_SIMPLE_COMMANDS.keys()),
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

KODI_REMOTE_UI_PAGES: [UiPage] = [
    {
        "page_id": "Kodi commands",
        "name": "Kodi commands",
        "grid": {"width": 4, "height": 6},
        "items": [
            {
                "command": {"cmd_id": "remote.send", "params": {"command": Commands.INFO, "repeat": 1}},
                "icon": "uc:info",
                "location": {"x": 0, "y": 0},
                "size": {"height": 1, "width": 1},
                "type": "icon",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": Commands.AUDIO_TRACK, "repeat": 1}},
                "icon": "uc:language",
                "location": {"x": 1, "y": 0},
                "size": {"height": 1, "width": 1},
                "type": "icon",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": Commands.SUBTITLE, "repeat": 1}},
                "icon": "uc:cc",
                "location": {"x": 2, "y": 0},
                "size": {"height": 1, "width": 1},
                "type": "icon",
            },
            {
                "command": {"cmd_id": "MODE_SHOW_SUBTITLES"},
                "text": "Toggle subtitles",
                "location": {"x": 3, "y": 0},
                "size": {"height": 1, "width": 1},
                "type": "text",
            },
            {
                "command": {"cmd_id": "MODE_FULLSCREEN"},
                "text": "Full screen",
                "location": {"x": 0, "y": 1},
                "size": {"height": 1, "width": 1},
                "type": "text",
            },
            {
                "command": {"cmd_id": "MODE_ZOOM_IN"},
                "text": "Zoom in",
                "location": {"x": 1, "y": 1},
                "size": {"height": 1, "width": 1},
                "type": "text",
            },
            {
                "command": {"cmd_id": "MODE_ZOOM_OUT"},
                "text": "Zoom out",
                "location": {"x": 2, "y": 1},
                "size": {"height": 1, "width": 1},
                "type": "text",
            },
            {
                "command": {"cmd_id": Commands.CONTEXT_MENU},
                "icon": "uc:menu",
                "location": {"x": 3, "y": 5},
                "size": {"height": 1, "width": 1},
                "type": "icon",
            },
        ],
    },
    {
        "page_id": "Kodi numbers",
        "name": "Kodi numbers",
        "grid": {"height": 4, "width": 3},
        "items": [
            {
                "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_1, "repeat": 1}},
                "location": {"x": 0, "y": 0},
                "size": {"height": 1, "width": 1},
                "text": "1",
                "type": "text",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_2, "repeat": 1}},
                "location": {"x": 1, "y": 0},
                "size": {"height": 1, "width": 1},
                "text": "2",
                "type": "text",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_3, "repeat": 1}},
                "location": {"x": 2, "y": 0},
                "size": {"height": 1, "width": 1},
                "text": "3",
                "type": "text",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_4, "repeat": 1}},
                "location": {"x": 0, "y": 1},
                "size": {"height": 1, "width": 1},
                "text": "4",
                "type": "text",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_5, "repeat": 1}},
                "location": {"x": 1, "y": 1},
                "size": {"height": 1, "width": 1},
                "text": "5",
                "type": "text",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_6, "repeat": 1}},
                "location": {"x": 2, "y": 1},
                "size": {"height": 1, "width": 1},
                "text": "6",
                "type": "text",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_7, "repeat": 1}},
                "location": {"x": 0, "y": 2},
                "size": {"height": 1, "width": 1},
                "text": "7",
                "type": "text",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_8, "repeat": 1}},
                "location": {"x": 1, "y": 2},
                "size": {"height": 1, "width": 1},
                "text": "8",
                "type": "text",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_9, "repeat": 1}},
                "location": {"x": 2, "y": 2},
                "size": {"height": 1, "width": 1},
                "text": "9",
                "type": "text",
            },
            {
                "command": {"cmd_id": "remote.send", "params": {"command": Commands.DIGIT_0, "repeat": 1}},
                "location": {"x": 1, "y": 3},
                "size": {"height": 1, "width": 1},
                "text": "0",
                "type": "text",
            },
        ],
    },
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
