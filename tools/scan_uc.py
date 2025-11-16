"""
Test connection script for Kodi integration driver.

:copyright: (c) 2025 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""
import argparse
# pylint: disable=all
# flake8: noqa

import asyncio
import logging
import sys
from typing import Any

import jsonrpc_base
from rich import print_json

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)

from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

# pylint: disable = W1405
LOOKUP_TIMEOUT = 5
LOOKUP_DURATION = 10
_LOG = logging.getLogger(__name__)


class UCDiscover(ServiceListener):
    """Kodi instance discovery."""

    _services_found = []

    async def discover(self, zero_conf_lookup_string: str) -> list[Any]:
        """Discover instances."""
        self._services_found:list[dict[str, any]] = []
        zeroconf = Zeroconf()
        ServiceBrowser(zeroconf, zero_conf_lookup_string, self)
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
        item = {"server": server, "ip": ip, "port": port, "name": name, "id": _id, "info": info}
        self._services_found.append(item)
        print_json(data={"server": server, "ip": ip, "port": port, "name": name, "id": _id})
        # _LOG.debug("Discovered service %s : %s", name, info)


async def main():
    _LOG.debug("Start scan")
    parser = argparse.ArgumentParser(
        prog='scan_uc.py',
        description='Scan network for UC remotes or docks')
    parser.add_argument('-d', '--dock',
                        action='store_true', help="Scan for docks")
    parser.add_argument('-r', '--remote',
                        action='store_true', help="Scan for remotes")
    args = parser.parse_args()
    print(args)
    if args.dock is False and args.remote is False:
        parser.print_help()
        exit(0)
    if args.dock is True and args.remote is True:
        parser.print_help()
        exit(0)

    zero_conf_lookup_string = "_uc-dock._tcp.local." if args.dock else "_uc-remote._tcp.local."
    try:
        discovery = UCDiscover()
        _discovered_ucs = await discovery.discover(zero_conf_lookup_string)
        _LOG.debug("Discovered UC devices : %s", _discovered_ucs)
    # pylint: disable = W0718
    except Exception as ex:
        _LOG.error("Error during devices discovery %s", ex)
    # await pair()
    # exit(0)

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
    jsonrpc_base.Server.__register = register_rpc

    logging.getLogger(__name__).setLevel(logging.DEBUG)
    _LOOP.run_until_complete(main())
    _LOOP.run_forever()
