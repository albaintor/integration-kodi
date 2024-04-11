"""Constants used for Kodi integration."""
from ucapi.media_player import Features, MediaType, Commands

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
    "MENU_VIDEO" : "showvideomenu",
    "MODE_FULLSCREEN": "togglefullscreen",
    "MODE_ZOOM_IN" : "zoomin",
    "MODE_ZOOM_OUT" : "zoomout",
    "MODE_INCREASE_PAR" : "increasepar",
    "MODE_DECREASE_PAR" : "decreasepar",
    "MODE_SHOW_SUBTITLES" : "showsubtitles",
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
}

# @see: https://github.com/xbmc/xbmc/blob/master/system/keymaps/remote.xml
KODI_BUTTONS_KEYMAP = {
    Commands.CHANNEL_UP: "pageplus",
    Commands.CHANNEL_DOWN: "pageminus",
    Commands.CURSOR_UP: "up",
    Commands.CURSOR_DOWN: "down",
    Commands.CURSOR_LEFT: "left",
    Commands.CURSOR_RIGHT: "right",
    Commands.CURSOR_ENTER: "select",
    Commands.BACK: "back",
    Commands.DIGIT_0: "zero",
    Commands.DIGIT_1: "one",
    Commands.DIGIT_2: "two",
    Commands.DIGIT_3: "three",
    Commands.DIGIT_4: "four",
    Commands.DIGIT_5: "five",
    Commands.DIGIT_6: "six",
    Commands.DIGIT_7: "seven",
    Commands.DIGIT_8: "eight",
    Commands.DIGIT_9: "nine",
    Commands.GUIDE: "guide",
    Commands.RECORD: "record",
    Commands.INFO: "info"
}
