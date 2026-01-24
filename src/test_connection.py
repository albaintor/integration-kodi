"""
Test connection script for Kodi integration driver.

:copyright: (c) 2025 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

# pylint: disable=all
# flake8: noqa

import asyncio
import logging
import sys
from typing import Any

import jsonrpc_base
from rich import print_json
from ucapi import Events

import kodi
from config import KodiConfigDevice
from kodi import KodiDevice
from media_player import KodiMediaPlayer

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)

address = "192.168.1.60"  # PC
# address = "192.168.1.45"  # Mac
# address = "192.168.1.20"  # Shield
username = "kodi"
password = "ludi"


async def on_device_update(device_id: str, update: dict[str, Any] | None) -> None:
    print("Device update : " + device_id)
    print_json(data=update)


async def on_entity_attributes_updated(entity_id: str, entity_type: str, update: dict[str, Any] | None) -> None:
    print("Attribute update : " + entity_id)
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
            show_stream_name=True,
            show_stream_language_name=True,
        )
    )
    # await client.power_on()
    client.events.on(kodi.Events.UPDATE, on_device_update)
    client.events.on(Events.ENTITY_ATTRIBUTES_UPDATED, on_entity_attributes_updated)
    await client.connect()

    await asyncio.sleep(2)
    # properties = client._item
    # print("Properties :")
    # print_json(data=properties)

    # await asyncio.sleep(4)
    # await client.select_audio_track("French FR (VFF Remix Surround 5.1 (tonalité correcte), DVD PAL FRA) DTS-HD MA 5.1")
    # properties = await client.get_chapters()
    # print_json(data=properties)

    properties = await client.get_app_language()
    print_json(data=properties)
    properties = await client.get_name()
    print_json(data=properties)

    await asyncio.sleep(600)

    # await KodiMediaPlayer.mediaplayer_command("entityid", client, "key yellow KB 0")
    # await KodiMediaPlayer.mediaplayer_command("entityid", client, "action nextchannelgroup")
    # await KodiMediaPlayer.mediaplayer_command("entityid", client, "action nextchannelgroup")
    # await KodiMediaPlayer.mediaplayer_command("entityid", client, "System.Shutdown")
    # await KodiMediaPlayer.mediaplayer_command("entityid", client, "Input.ExecuteAction {\"action\":\"subtitledelayminus\"}")
    # await KodiMediaPlayer.mediaplayer_command("entityid", client, "audiodelay 0.1")
    # await KodiMediaPlayer.mediaplayer_command(
    #     "entityid", client, 'Player.SetAudioDelay {"playerid":PID,"offset":"increment"}'
    # )
    # await KodiMediaPlayer.mediaplayer_command("entity.media_player", client, "activatewindow shutdownmenu")
    # await client.call_command("GUI.ActivateWindow", **{"window": "settings"})
    # await client.command_action("dialogselectsubtitle")
    # await client.command_action("dialogselectaudio")
    # await client.call_command("GUI.ActivateWindow", **{"window": "dialogselectaudio"})
    # await client.call_command("GUI.ActivateWindow", **{"window": "dialogselectaudio"})
    # await KodiMediaPlayer.mediaplayer_command("entityid", client, "audio_track")
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


def register_rpc(self, method_name, callback):
    _LOG.debug("Register %s", method_name)
    self._server_request_handlers[method_name] = callback


if __name__ == "__main__":
    _LOG = logging.getLogger(__name__)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logging.basicConfig(handlers=[ch])
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    logging.getLogger("client").setLevel(logging.DEBUG)
    logging.getLogger("media_player").setLevel(logging.DEBUG)
    logging.getLogger("remote").setLevel(logging.DEBUG)
    logging.getLogger("kodi").setLevel(logging.DEBUG)
    logging.getLogger("pykodi.kodi").setLevel(logging.DEBUG)
    jsonrpc_base.Server.__register = register_rpc

    logging.getLogger(__name__).setLevel(logging.DEBUG)
    _LOOP.run_until_complete(main())
    _LOOP.run_forever()
