"""
Test connection script for Kodi integration driver.

:copyright: (c) 2025 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
import sys
from typing import Any

from rich import print_json
from kodi import KodiDevice
from config import KodiConfigDevice
import kodi

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)

address = "192.168.1.20"
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
            artwork_type=0,
            media_update_task=True
        )
    )
    # await client.power_on()
    client.events.on(kodi.Events.UPDATE, on_device_update)
    await client.connect()

    await asyncio.sleep(4)
    #properties = client._item
    #print("Properties :")
    #print_json(data=properties)
    await client.play_pause()
    await asyncio.sleep(4)
    await client.play_pause()
    # power_state = await client._tv.get_power_state()
    # _LOG.debug("Power state %s", power_state)
    # tv_info = client._tv.tv_info
    # _LOG.debug("TV Info %s", tv_info)

    # Validate pairing key (77)
    # await client.button("ENTER")

    # Validate pairing key (55)



if __name__ == "__main__":
    _LOG = logging.getLogger(__name__)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logging.basicConfig(handlers=[ch])
    logging.getLogger("client").setLevel(logging.DEBUG)
    logging.getLogger("kodi").setLevel(logging.DEBUG)
    logging.getLogger("pykodi.kodi").setLevel(logging.DEBUG)
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    _LOOP.run_until_complete(main())
    _LOOP.run_forever()
