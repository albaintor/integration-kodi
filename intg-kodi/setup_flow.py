"""
Setup flow for LG TV integration.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
from enum import IntEnum

from aiohttp import ClientSession
from pykodi.kodi import KodiWSConnection, KodiConnection, Kodi, CannotConnectError, InvalidAuthError, KodiHTTPConnection

import config
from config import KodiConfigDevice
from ucapi import (
    AbortDriverSetup,
    DriverSetupRequest,
    IntegrationSetupError,
    RequestUserInput,
    SetupAction,
    SetupComplete,
    SetupDriver,
    SetupError,
    UserDataResponse,
)

_LOG = logging.getLogger(__name__)


# TODO to be confirmed : Home assistant configured zeroconf url "_xbmc-jsonrpc-h._tcp.local."
# but it was not advertised at all on my network so I didn't code discovery
class SetupSteps(IntEnum):
    """Enumeration of setup steps to keep track of user data responses."""

    INIT = 0
    CONFIGURATION_MODE = 1
    CONFIGURE_DEVICE = 2


_setup_step = SetupSteps.INIT
_cfg_add_device: bool = False
_pairing_device: KodiConnection | None = None
_pairing_device_ws: KodiWSConnection | None = None
_user_input_discovery = RequestUserInput(
    {"en": "Setup mode", "de": "Setup Modus", "fr": "Configuration"},
    [
        {
            "id": "info",
            "label": {
                "en": "Configure your Kodi devices",
                "de": "Verbinde auf Kodi Gerät",
                "fr": "Connexion à votre instance Kodi",
            },
            "field": {
                "label": {
                    "value": {
                        "en": "Kodi must be running, and control enabled from Settings > Services > Control section. Port numbers shouldn't be modified.",
                        "fr": "Kodi doit être lancé et le contrôle activé depuis les Paramètres > Services > Contrôle. Laisser les numéros des ports inchangés.",
                    }
                }
            },
        },
        {
            "field": {"text": {"value": ""}},
            "id": "address",
            "label": {"en": "IP address", "de": "IP-Adresse", "fr": "Adresse IP"},
        },
        {
            "field": {"text": {"value": ""}},
            "id": "username",
            "label": {"en": "Username", "fr": "Utilisateur"},
        },
        {
            "field": {"text": {"value": ""}},
            "id": "password",
            "label": {"en": "Password", "fr": "Mot de passe"},
        },
        {
            "field": {"text": {"value": "9090"}},
            "id": "ws_port",
            "label": {"en": "Websocket port", "fr": "Port websocket"},
        },
        {
            "field": {"text": {"value": "8080"}},
            "id": "port",
            "label": {"en": "HTTP port", "fr": "Port HTTP"},
        },
        {
            "field": {"checkbox": {"value": False}},
            "id": "ssl",
            "label": {"en": "Use SSL", "fr": "Utiliser SSL"},
        },
    ],
)


async def driver_setup_handler(msg: SetupDriver) -> SetupAction:
    """
    Dispatch driver setup requests to corresponding handlers.

    Either start the setup process or handle the selected LG TV device.

    :param msg: the setup driver request object, either DriverSetupRequest or UserDataResponse
    :return: the setup action on how to continue
    """
    global _setup_step
    global _cfg_add_device

    if isinstance(msg, DriverSetupRequest):
        _setup_step = SetupSteps.INIT
        _cfg_add_device = False
        return await handle_driver_setup(msg)
    if isinstance(msg, UserDataResponse):
        _LOG.debug(msg)
        if _setup_step == SetupSteps.CONFIGURATION_MODE and "action" in msg.input_values:
            return await handle_configuration_mode(msg)
        if _setup_step == SetupSteps.CONFIGURE_DEVICE and "address" in msg.input_values:
            return await _handle_configuration(msg)
        _LOG.error("No or invalid user response was received: %s", msg)
    elif isinstance(msg, AbortDriverSetup):
        _LOG.info("Setup was aborted with code: %s", msg.error)
        if _pairing_device is not None:
            await _pairing_device.close()
            _pairing_android_tv = None
        _setup_step = SetupSteps.INIT

    # user confirmation not used in setup process
    # if isinstance(msg, UserConfirmationResponse):
    #     return handle_user_confirmation(msg)

    return SetupError()


async def handle_driver_setup(msg: DriverSetupRequest) -> RequestUserInput | SetupError:
    """
    Start driver setup.

    Initiated by Remote Two to set up the driver.
    Ask user to enter ip-address for manual configuration, otherwise auto-discovery is used.

    :param msg: not used, we don't have any input fields in the first setup screen.
    :return: the setup action on how to continue
    """
    global _setup_step

    # workaround for web-configurator not picking up first response
    await asyncio.sleep(1)

    reconfigure = msg.reconfigure
    _LOG.debug("Starting driver setup, reconfigure=%s", reconfigure)
    if reconfigure:
        _setup_step = SetupSteps.CONFIGURATION_MODE

        # get all configured devices for the user to choose from
        dropdown_devices = []
        for device in config.devices.all():
            dropdown_devices.append({"id": device.id, "label": {"en": f"{device.name} ({device.id})"}})

        # TODO #12 externalize language texts
        # build user actions, based on available devices
        dropdown_actions = [
            {
                "id": "add",
                "label": {
                    "en": "Add a new device",
                    "de": "Neues Gerät hinzufügen",
                    "fr": "Ajouter un nouvel appareil",
                },
            },
        ]

        # add remove & reset actions if there's at least one configured device
        if dropdown_devices:
            dropdown_actions.append(
                {
                    "id": "remove",
                    "label": {
                        "en": "Delete selected device",
                        "de": "Selektiertes Gerät löschen",
                        "fr": "Supprimer l'appareil sélectionné",
                    },
                },
            )
            dropdown_actions.append(
                {
                    "id": "reset",
                    "label": {
                        "en": "Reset configuration and reconfigure",
                        "de": "Konfiguration zurücksetzen und neu konfigurieren",
                        "fr": "Réinitialiser la configuration et reconfigurer",
                    },
                },
            )
        else:
            # dummy entry if no devices are available
            dropdown_devices.append({"id": "", "label": {"en": "---"}})

        return RequestUserInput(
            {"en": "Configuration mode", "de": "Konfigurations-Modus"},
            [
                {
                    "field": {"dropdown": {"value": dropdown_devices[0]["id"], "items": dropdown_devices}},
                    "id": "choice",
                    "label": {
                        "en": "Configured devices",
                        "de": "Konfigurierte Geräte",
                        "fr": "Appareils configurés",
                    },
                },
                {
                    "field": {"dropdown": {"value": dropdown_actions[0]["id"], "items": dropdown_actions}},
                    "id": "action",
                    "label": {
                        "en": "Action",
                        "de": "Aktion",
                        "fr": "Appareils configurés",
                    },
                },
            ],
        )

    # Initial setup, make sure we have a clean configuration
    config.devices.clear()  # triggers device instance removal
    _setup_step = SetupSteps.CONFIGURE_DEVICE
    return _user_input_discovery


async def handle_configuration_mode(msg: UserDataResponse) -> RequestUserInput | SetupComplete | SetupError:
    """
    Process user data response in a setup process.

    If ``address`` field is set by the user: try connecting to device and retrieve model information.
    Otherwise, start Android TV discovery and present the found devices to the user to choose from.

    :param msg: response data from the requested user data
    :return: the setup action on how to continue
    """
    global _setup_step
    global _cfg_add_device

    action = msg.input_values["action"]

    # workaround for web-configurator not picking up first response
    await asyncio.sleep(1)

    match action:
        case "add":
            _cfg_add_device = True
        case "remove":
            choice = msg.input_values["choice"]
            if not config.devices.remove(choice):
                _LOG.warning("Could not remove device from configuration: %s", choice)
                return SetupError(error_type=IntegrationSetupError.OTHER)
            config.devices.store()
            return SetupComplete()
        case "reset":
            config.devices.clear()  # triggers device instance removal
        case _:
            _LOG.error("Invalid configuration action: %s", action)
            return SetupError(error_type=IntegrationSetupError.OTHER)

    _setup_step = SetupSteps.CONFIGURE_DEVICE
    return _user_input_discovery


async def _handle_configuration(msg: UserDataResponse) -> SetupComplete | SetupError:
    """
    Process user data response in a setup process.

    If ``address`` field is set by the user: try connecting to device and retrieve model information.
    Otherwise, start LG TV discovery and present the found devices to the user to choose from.

    :param msg: response data from the requested user data
    :return: the setup action on how to continue
    """
    global _pairing_device
    global _pairing_device_ws
    global _setup_step

    # clear all configured devices and any previous pairing attempt
    if _pairing_device:
        try:
            await _pairing_device.close()
        except Exception:
            pass
        _pairing_device = None
    if _pairing_device_ws:
        try:
            await _pairing_device_ws.close()
        except Exception:
            pass
        _pairing_device_ws = None

    dropdown_items = []
    address = msg.input_values["address"]
    port = msg.input_values["port"]
    ws_port = msg.input_values["ws_port"]
    username = msg.input_values["username"]
    password = msg.input_values["password"]
    ssl = msg.input_values["ssl"]
    if ssl == 'false':
        ssl = False
    else:
        ssl = True

    _LOG.debug("Starting driver setup for %s, port %s, websocket port %s, username %s, ssl %s", address, port, ws_port,
               username, ssl)
    try:
        # simple connection check
        async with ClientSession(raise_for_status=True) as session:
            device = KodiHTTPConnection(host=address, port=port, username=username, password=password,
                                        timeout=5, session=session, ssl=ssl)
            kodi = Kodi(device)
            try:
                await kodi.ping()
                _LOG.debug("Connection %s:%s succeeded over HTTP", address, port)
            except CannotConnectError:
                _LOG.warning("Cannot connect to %s:%s over HTTP [%s]", address, port)
                return SetupError(error_type=IntegrationSetupError.CONNECTION_REFUSED)
            except InvalidAuthError:
                _LOG.warning("Authentication refused to %s:%s over HTTP", address, port)
                return SetupError(error_type=IntegrationSetupError.AUTHORIZATION_ERROR)
            device = KodiWSConnection(host=address, port=port, ws_port=ws_port,
                                      username=username, password=password, ssl=ssl, timeout=5, session=session)
            try:
                await device.connect()
                if not device.connected:
                    _LOG.warning("Cannot connect to %s:%s over WebSocket", address, ws_port)
                    return SetupError(error_type=IntegrationSetupError.CONNECTION_REFUSED)
                kodi = Kodi(device)
                await kodi.ping()
                await device.close()
                _LOG.debug("Connection %s:%s succeeded over websocket", address, port)
            except CannotConnectError as error:
                _LOG.warning("Cannot connect to %s:%s over WebSocket", address, ws_port)
                return SetupError(error_type=IntegrationSetupError.CONNECTION_REFUSED)

            dropdown_items.append({"id": address, "label": {"en": f"Kodi [{address}]"}})
    except Exception as ex:
        _LOG.error("Cannot connect to manually entered address %s: %s", address, ex)
        return SetupError(error_type=IntegrationSetupError.CONNECTION_REFUSED)

    # TODO improve device ID (IP actually)
    config.devices.add(
        KodiConfigDevice(id=address, name="Kodi", address=address, username=username,
                         password=password, port=port, ws_port=ws_port, ssl=ssl)
    )  # triggers SonyLG TV instance creation
    config.devices.store()

    await asyncio.sleep(1)
    _LOG.info("Setup successfully completed for %s", address)
    return SetupComplete()
