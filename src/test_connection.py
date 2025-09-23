"""
Test connection script for Kodi integration driver.

:copyright: (c) 2025 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

# pylint: disable=all

import asyncio
import logging
import sys
from typing import Any

from rich import print_json

import kodi
from config import KodiConfigDevice
from kodi import KodiDevice
from media_player import KodiMediaPlayer

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)

address = "192.168.1.3"
# address = "192.168.1.20"
username = "kodi"
password = "ludi"


async def on_device_update(device_id: str, update: dict[str, Any] | None) -> None:
    print_json(data=update)


async def main():
    _LOG.debug("Start connection")
    # await pair()
    # exit(0)
    client = KodiDevice(
        device_config=KodiConfigDevice(
            id="kodi",
            name="Kodi",
            address=address,
            port="8080",
            ws_port="9090",
            username=username,
            ssl=False,
            password=password,
            artwork_type="fanart",
            artwork_type_tvshows="season.banner",
            media_update_task=True,
            download_artwork=False,
            disable_keyboard_map=True,
        )
    )
    # await client.power_on()
    client.events.on(kodi.Events.UPDATE, on_device_update)
    await client.connect()

    await asyncio.sleep(2)
    properties = client._item
    print("Properties :")
    print_json(data=properties)
    await KodiMediaPlayer.mediaplayer_command("entity.media_player", client, "activatewindow shutdownmenu")
    # await client.call_command("GUI.ActivateWindow", **{"window": "settings"})
    # await client.command_action("dialogselectsubtitle")
    # await client.command_action("dialogselectaudio")
    # await client.call_command("GUI.ActivateWindow", **{"window": "dialogselectaudio"})
    # await client.call_command("GUI.ActivateWindow", **{"window": "dialogselectaudio"})
    # await client.play_pause()
    # await asyncio.sleep(4)
    # await client.play_pause()

    # Examples :
    await client._kodi.call_method("Input.Down")
    # await client._kodi._server.Input.Down()
    # command = KODI_ALTERNATIVE_BUTTONS_KEYMAP[Commands.CURSOR_DOWN]
    # await client.call_command(command["method"], **command["params"])

    # command = KODI_ALTERNATIVE_BUTTONS_KEYMAP[Commands.CHANNEL_DOWN]
    # await client.call_command(command["method"], **command["params"])

    # await client.command_action(KODI_SIMPLE_COMMANDS["MODE_FULLSCREEN"])
    # await client.call_command("GUI.SetFullscreen", **{"fullscreen": "toggle"})
    # await client.call_command("GUI.ActivateWindow", **{"window": "osdsubtitlesettings"})

    exit(0)


if __name__ == "__main__":
    _LOG = logging.getLogger(__name__)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logging.basicConfig(handlers=[ch])
    logging.getLogger("client").setLevel(logging.DEBUG)
    logging.getLogger("media_player").setLevel(logging.DEBUG)
    logging.getLogger("remote").setLevel(logging.DEBUG)
    logging.getLogger("kodi").setLevel(logging.DEBUG)
    logging.getLogger("pykodi.kodi").setLevel(logging.DEBUG)
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    _LOOP.run_until_complete(main())
    _LOOP.run_forever()
