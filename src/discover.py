"""
This module implements a Remote Two integration driver for Kodi receivers.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

# pylint: disable = W1405
ZERO_CONF_LOOKUP_STRING = "_xbmc-jsonrpc-h._tcp.local."
LOOKUP_TIMEOUT = 5
LOOKUP_DURATION = 10
_LOG = logging.getLogger(__name__)


class KodiDiscover(ServiceListener):
    """Kodi instance discovery."""

    _services_found = []

    async def discover(self) -> []:
        """Discover instances."""
        self._services_found = []
        zeroconf = Zeroconf()
        ServiceBrowser(zeroconf, ZERO_CONF_LOOKUP_STRING, self)
        await asyncio.sleep(LOOKUP_DURATION)
        zeroconf.close()
        _LOG.debug("Discovery services found %s", self._services_found)
        return self._services_found

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Update entry."""
        # print(f"Service {name} updated")

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Remove entry."""
        # print(f"Service {name} removed")

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Add entry."""
        info = zc.get_service_info(type_, name, LOOKUP_TIMEOUT)
        ip = info.parsed_addresses()[0]
        server = info.server
        name = info.name
        port = info.port
        _id = server
        try:
            _id = info.properties[b"uuid"].decode("ascii")
        # pylint: disable = W0718
        except Exception:
            pass
        self._services_found.append({"server": server, "ip": ip, "port": port, "name": name, "id": _id, "info": info})
        _LOG.debug("Discovered service %s : %s", name, info)
