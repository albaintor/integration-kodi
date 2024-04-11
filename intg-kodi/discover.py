import asyncio
import logging

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

ZERO_CONF_LOOKUP_STRING = "_xbmc-jsonrpc-h._tcp.local."
LOOKUP_TIMEOUT = 5
LOOKUP_DURATION = 10
_LOG = logging.getLogger(__name__)


class KodiDiscover(ServiceListener):
    _services_found = []

    async def discover(self) -> []:
        self._services_found = []
        zeroconf = Zeroconf()
        ServiceBrowser(zeroconf, ZERO_CONF_LOOKUP_STRING, self)
        await asyncio.sleep(LOOKUP_DURATION)
        zeroconf.close()
        _LOG.debug("Discovery services found %s", self._services_found)
        return self._services_found
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        # print(f"Service {name} updated")
        pass

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        # print(f"Service {name} removed")
        pass

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name, LOOKUP_TIMEOUT)
        ip = info.parsed_addresses()[0]
        server = info.server
        name = info.name
        port = info.port
        id = server
        try:
            id = info.properties[b'uuid'].decode('ascii')
        except Exception:
            pass
        self._services_found.append({'server': server, 'ip': ip, 'port': port, 'name': name, 'id': id, 'info': info})
        _LOG.debug("Discovered service %s : %s", name, info)
