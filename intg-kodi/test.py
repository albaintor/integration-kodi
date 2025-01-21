import asyncio

from aiohttp import ClientSession

from pykodi.kodi import (
    CannotConnectError,
    InvalidAuthError,
    Kodi,
    KodiConnection,
    KodiHTTPConnection,
    KodiWSConnection,
)

async def main():
    async with ClientSession(raise_for_status=True) as session:
        device = KodiWSConnection(
                        host="192.168.1.30",
                        port="8080",
                        ws_port="9090",
                        username="kodi",
                        password="ludi",
                        ssl=False,
                        timeout=5,
                        session=session,
                    )
        await device.connect()

loop = asyncio.get_event_loop()
loop.run_until_complete(main())