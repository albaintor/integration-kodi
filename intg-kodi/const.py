"""Constants used for Kodi integration."""
from ucapi.media_player import Features, MediaType, Commands
from typing import TypedDict

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
    Commands.DIGIT_0: {"button": "numpadzero"},
    Commands.DIGIT_1: {"button": "numpadone"},
    Commands.DIGIT_2: {"button": "numpadtwo"},
    Commands.DIGIT_3: {"button": "numpadthree"},
    Commands.DIGIT_4: {"button": "numpadfour"},
    Commands.DIGIT_5: {"button": "numpadfive"},
    Commands.DIGIT_6: {"button": "numpadsix"},
    Commands.DIGIT_7: {"button": "numpadseven"},
    Commands.DIGIT_8: {"button": "numpadeight"},
    Commands.DIGIT_9: {"button": "numpadnine"},
    Commands.RECORD: {"button": "record", "keymap": "R1"},
    Commands.GUIDE: {"button": "guide", "keymap": "R1"},
}
