"""Constants used for Kodi integration."""
from ucapi.media_player import Features, MediaType, Commands
from typing import TypedDict

from ucapi.ui import DeviceButtonMapping, Buttons, UiPage

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
    "MENU_VIDEO": "showvideomenu",
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
}

# Taken from https://kodi.wiki/view/JSON-RPC_API/v10#Input.Action
# (expand schema description),
# more info also on https://forum.kodi.tv/showthread.php?tid=349151 which explains the logic
KODI_ACTIONS_KEYMAP = {
    Commands.SUBTITLE: "nextsubtitle",
    Commands.AUDIO_TRACK: "audionextlanguage",
    Commands.FAST_FORWARD: "fastforward",
    Commands.REWIND: "rewind",
    Commands.FUNCTION_GREEN: "green",
    Commands.FUNCTION_BLUE: "blue",
    Commands.FUNCTION_RED: "red",
    Commands.FUNCTION_YELLOW: "yellow",
    Commands.MENU: "menu",
    Commands.INFO: "info"
}


class BUTTON_KEYMAP(TypedDict):
    button: str
    keymap: str | None
    holdtime: int | None


# Taken from https://kodi.wiki/view/List_of_keynames,
# For remote buttons see https://github.com/xbmc/xbmc/blob/master/system/keymaps/remote.xml
KODI_BUTTONS_KEYMAP: dict[str, BUTTON_KEYMAP] = {
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
}

KODI_REMOTE_BUTTONS_MAPPING: [DeviceButtonMapping] = [
    {"button": Buttons.BACK, "short_press":  {"cmd_id": Commands.BACK}},
    {"button": Buttons.HOME, "short_press":  {"cmd_id": Commands.HOME}},
    {"button": Buttons.CHANNEL_DOWN, "short_press":  {"cmd_id": Commands.CHANNEL_DOWN}},
    {"button": Buttons.CHANNEL_UP, "short_press":  {"cmd_id": Commands.CHANNEL_UP}},
    {"button": Buttons.DPAD_UP, "short_press":  {"cmd_id": Commands.CURSOR_UP}},
    {"button": Buttons.DPAD_DOWN, "short_press":  {"cmd_id": Commands.CURSOR_DOWN}},
    {"button": Buttons.DPAD_LEFT, "short_press":  {"cmd_id": Commands.CURSOR_LEFT}},
    {"button": Buttons.DPAD_RIGHT, "short_press":  {"cmd_id": Commands.CURSOR_RIGHT}},
    {"button": Buttons.DPAD_MIDDLE, "short_press":  {"cmd_id": Commands.CURSOR_ENTER}},
    {"button": Buttons.PLAY, "short_press":  {"cmd_id": Commands.PLAY_PAUSE}},
    {"button": Buttons.PREV, "short_press":  {"cmd_id": Commands.PREVIOUS}},
    {"button": Buttons.NEXT, "short_press":  {"cmd_id": Commands.NEXT}},
    {"button": Buttons.VOLUME_UP, "short_press":  {"cmd_id": Commands.VOLUME_UP}},
    {"button": Buttons.VOLUME_DOWN, "short_press":  {"cmd_id": Commands.VOLUME_DOWN}},
    {"button": Buttons.MUTE, "short_press":  {"cmd_id": Commands.MUTE_TOGGLE}},
]

# All defined commands for remote entity
KODI_REMOTE_SIMPLE_COMMANDS = [
    *list(KODI_SIMPLE_COMMANDS.keys()),
    *list(KODI_ACTIONS_KEYMAP.keys()),
    *list(KODI_BUTTONS_KEYMAP.keys())
]

KODI_REMOTE_UI_PAGES: [UiPage] = [
    {
        "page_id": "Kodi commands",
        "name": "Kodi commands",
        "grid": {"width": 4, "height": 6},
        "items": [
            {
                "command": {
                    "cmd_id": "remote.send",
                    "params": {"command": Commands.AUDIO_TRACK, "repeat": 1}
                },
                "icon": "uc:language",
                "location": {
                    "x": 1,
                    "y": 0
                },
                "size": {
                    "height": 1,
                    "width": 1
                },
                "type": "icon"
            },
            {
                 "command": {
                    "cmd_id": "remote.send",
                    "params": {"command": Commands.SUBTITLE, "repeat": 1}
                },
                "icon": "uc:cc",
                "location": {
                    "x": 2,
                    "y": 0
                },
                "size": {
                    "height": 1,
                    "width": 1
                },
                "type": "icon"
            },
            {
                "command": {
                    "cmd_id": "remote.send",
                    "params": {"command": Commands.CONTEXT_MENU, "repeat": 1}
                },
                "icon": "uc:menu",
                "location": {
                    "x": 3,
                    "y": 5
                },
                "size": {
                    "height": 1,
                    "width": 1
                },
                "type": "icon"
            },
        ]
    }
]