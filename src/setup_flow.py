"""
Setup flow for LG TV integration.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
from enum import IntEnum

import config
from aiohttp import ClientSession
from config import KodiConfigDevice
from discover import KodiDiscover
from pykodi.kodi import (
    CannotConnectError,
    InvalidAuthError,
    Kodi,
    KodiConnection,
    KodiHTTPConnection,
    KodiWSConnection,
)
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

from const import KODI_ARTWORK_LABELS, KODI_ARTWORK_TVSHOWS_LABELS, KODI_DEFAULT_ARTWORK, KODI_DEFAULT_TVSHOW_ARTWORK
from src.config import ConfigImportResult

_LOG = logging.getLogger(__name__)


# pylint: disable = C0301,W1405
# flake8: noqa


# TODO to be confirmed : Home assistant configured zeroconf url "_xbmc-jsonrpc-h._tcp.local."
# but it was not advertised at all on my network so I didn't code discovery
class SetupSteps(IntEnum):
    """Enumeration of setup steps to keep track of user data responses."""

    INIT = 0
    WORKFLOW_MODE = 1
    DEVICE_CONFIGURATION_MODE = 2
    DISCOVER = 3
    DEVICE_CHOICE = 4
    RECONFIGURE = 5
    BACKUP_RESTORE = 6


_setup_step = SetupSteps.INIT
_cfg_add_device: bool = False
_discovered_kodis: list[dict[str, str]] = []
_pairing_device: KodiConnection | None = None
_pairing_device_ws: KodiWSConnection | None = None
_reconfigured_device: KodiConfigDevice | None = None

# pylint: disable = R0911
_user_input_manual = RequestUserInput(
    {"en": "Setup mode", "de": "Setup Modus", "fr": "Installation"},
    [
        {
            "id": "info",
            "label": {
                "en": "Discover or connect to Kodi instances. Leave address blank for automatic discovery.",
                "fr": "Découverte ou connexion à vos instances Kodi. Laisser le champ adresse vide pour la découverte automatique.",
                # noqa: E501
            },
            "field": {
                "label": {
                    "value": {
                        "en": "Kodi must be running, and control enabled from Settings > Services > Control section. Port numbers shouldn't be modified.",
                        # noqa: E501
                        "fr": "Kodi doit être lancé et le contrôle activé depuis les Paramètres > Services > Contrôle. Laisser les numéros des ports inchangés.",
                        # noqa: E501
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
        {
            "field": {"dropdown": {"value": KODI_DEFAULT_ARTWORK, "items": KODI_ARTWORK_LABELS}},
            "id": "artwork_type",
            "label": {
                "en": "Artwork type to display",
                "fr": "Type d'image média à afficher",
            },
        },
        {
            "field": {"dropdown": {"value": KODI_DEFAULT_TVSHOW_ARTWORK, "items": KODI_ARTWORK_TVSHOWS_LABELS}},
            "id": "artwork_type_tvshows",
            "label": {
                "en": "Artwork type to display for TV Shows",
                "fr": "Type d'image média à afficher pour les séries",
            },
        },
        {
            "field": {"checkbox": {"value": True}},
            "id": "media_update_task",
            "label": {"en": "Enable media update task", "fr": "Activer la tâche de mise à jour du média"},
        },
        {
            "field": {"checkbox": {"value": False}},
            "id": "download_artwork",
            "label": {
                "en": "Download artwork instead of transmitting URL to the remote",
                "fr": "Télécharger l'image au lieu de transmettre l'URL à la télécommande",
            },
        },
        {
            "field": {"checkbox": {"value": False}},
            "id": "disable_keyboard_map",
            "label": {
                "en": "Disable keyboard map : check only if some commands fail (eg arrow keys)",
                "fr": "Désactiver les commandes clavier : cocher uniquement si certaines commandes échouent "
                "(ex : commandes de direction)",
            },
        },
    ],
)


# pylint: disable=R0911
async def driver_setup_handler(msg: SetupDriver) -> SetupAction:
    """
    Dispatch driver setup requests to corresponding handlers.

    Either start the setup process or handle the selected LG TV device.

    :param msg: the setup driver request object, either DriverSetupRequest or UserDataResponse
    :return: the setup action on how to continue
    """
    global _setup_step
    global _cfg_add_device
    global _pairing_device
    global _pairing_device_ws

    if isinstance(msg, DriverSetupRequest):
        _setup_step = SetupSteps.INIT
        _cfg_add_device = False
        return await handle_driver_setup(msg)

    if isinstance(msg, UserDataResponse):
        _LOG.debug("Setup handler message : step %s, message : %s", _setup_step, msg)
        manual_config = False
        if _setup_step == SetupSteps.WORKFLOW_MODE:
            if msg.input_values.get("configuration_mode", "") == "normal":
                _setup_step = SetupSteps.DEVICE_CONFIGURATION_MODE
                _LOG.debug("Starting normal setup workflow")
                return _user_input_manual
            else:
                _LOG.debug("User requested backup/restore of configuration")
                return await _handle_backup_restore_step()
        if "address" in msg.input_values and len(msg.input_values["address"]) > 0:
            manual_config = True
        if _setup_step == SetupSteps.DEVICE_CONFIGURATION_MODE:
            if "action" in msg.input_values:
                _LOG.debug("Setup flow starts with existing configuration")
                return await handle_configuration_mode(msg)
            elif not manual_config:
                _LOG.debug("Setup flow in discovery mode")
                _setup_step = SetupSteps.DISCOVER
                return await handle_discovery(msg)
            else:
                _LOG.debug("Setup flow configuration mode")
                return await _handle_configuration(msg)
        # When user types an address at start (manual configuration)
        if _setup_step == SetupSteps.DISCOVER and manual_config:
            return await _handle_configuration(msg)
        # No address typed, discovery mode then
        if _setup_step == SetupSteps.DISCOVER:
            return await handle_discovery(msg)
        if _setup_step == SetupSteps.RECONFIGURE:
            return await _handle_device_reconfigure(msg)
        if _setup_step == SetupSteps.DEVICE_CHOICE and "choice" in msg.input_values:
            return await _handle_configuration(msg)
        if _setup_step == SetupSteps.BACKUP_RESTORE:
            return await _handle_backup_restore(msg)
        _LOG.error("No or invalid user response was received: %s (step %s)", msg, _setup_step)
    elif isinstance(msg, AbortDriverSetup):
        _LOG.info("Setup was aborted with code: %s", msg.error)
        # pylint: disable = W0718
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
    _LOG.debug("Handle driver setup, reconfigure=%s", reconfigure)
    if reconfigure:
        _setup_step = SetupSteps.DEVICE_CONFIGURATION_MODE

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
                    "id": "configure",
                    "label": {
                        "en": "Configure selected device",
                        "fr": "Configurer l'appareil sélectionné",
                    },
                },
            )
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

        dropdown_actions.append(
            {
                "id": "backup_restore",
                "label": {
                    "en": "Backup or restore devices configuration",
                    "fr": "Sauvegarder ou restaurer la configuration des appareils",
                },
            },
        )

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
    else:
        # Initial setup, make sure we have a clean configuration
        config.devices.clear()  # triggers device instance removal
        _setup_step = SetupSteps.WORKFLOW_MODE
        return RequestUserInput(
            {"en": "Configuration mode", "de": "Konfigurations-Modus"},
            [
                {
                    "field": {
                        "dropdown": {
                            "value": "normal",
                            "items": [
                                {
                                    "id": "normal",
                                    "label": {
                                        "en": "Start the configuration of the integration",
                                        "fr": "Démarrer la configuration de l'intégration",
                                    },
                                },
                                {
                                    "id": "backup_restore",
                                    "label": {
                                        "en": "Backup or restore devices configuration",
                                        "fr": "Sauvegarder ou restaurer la configuration des appareils",
                                    },
                                },
                            ],
                        }
                    },
                    "id": "configuration_mode",
                    "label": {
                        "en": "Configuration mode",
                        "fr": "Mode de configuration",
                    },
                }
            ],
        )


async def handle_configuration_mode(msg: UserDataResponse) -> RequestUserInput | SetupComplete | SetupError:
    """
    Process user data response in a setup process.

    If ``address`` field is set by the user: try connecting to device and retrieve model information.
    Otherwise, start instances discovery and present the found devices to the user to choose from.

    :param msg: response data from the requested user data
    :return: the setup action on how to continue
    """
    global _setup_step
    global _cfg_add_device
    global _reconfigured_device

    action = msg.input_values["action"]

    _LOG.debug("Handle configuration mode")

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
        case "configure":
            # Reconfigure device if the identifier has changed
            choice = msg.input_values["choice"]
            selected_device = config.devices.get(choice)
            if not selected_device:
                _LOG.warning("Can not configure device from configuration: %s", choice)
                return SetupError(error_type=IntegrationSetupError.OTHER)

            _setup_step = SetupSteps.RECONFIGURE
            _reconfigured_device = selected_device

            return RequestUserInput(
                {
                    "en": "Configure your Kodi device",
                    "fr": "Configurez votre appareil Kodi",
                },
                [
                    {
                        "field": {"text": {"value": _reconfigured_device.address}},
                        "id": "address",
                        "label": {"en": "IP address", "de": "IP-Adresse", "fr": "Adresse IP"},
                    },
                    {
                        "field": {"text": {"value": _reconfigured_device.username}},
                        "id": "username",
                        "label": {"en": "Username", "fr": "Utilisateur"},
                    },
                    {
                        "field": {"text": {"value": _reconfigured_device.password}},
                        "id": "password",
                        "label": {"en": "Password", "fr": "Mot de passe"},
                    },
                    {
                        "field": {"text": {"value": str(_reconfigured_device.ws_port)}},
                        "id": "ws_port",
                        "label": {"en": "Websocket port", "fr": "Port websocket"},
                    },
                    {
                        "field": {"text": {"value": str(_reconfigured_device.port)}},
                        "id": "port",
                        "label": {"en": "HTTP port", "fr": "Port HTTP"},
                    },
                    {
                        "field": {"checkbox": {"value": _reconfigured_device.ssl}},
                        "id": "ssl",
                        "label": {"en": "Use SSL", "fr": "Utiliser SSL"},
                    },
                    {
                        "field": {
                            "dropdown": {"value": _reconfigured_device.artwork_type, "items": KODI_ARTWORK_LABELS}
                        },
                        "id": "artwork_type",
                        "label": {
                            "en": "Artwork type to display",
                            "fr": "Type d'image média à afficher",
                        },
                    },
                    {
                        "field": {
                            "dropdown": {
                                "value": _reconfigured_device.artwork_type_tvshows,
                                "items": KODI_ARTWORK_TVSHOWS_LABELS,
                            }
                        },
                        "id": "artwork_type_tvshows",
                        "label": {
                            "en": "Artwork type to display for TV Shows",
                            "fr": "Type d'image média à afficher pour les séries",
                        },
                    },
                    {
                        "field": {"checkbox": {"value": _reconfigured_device.media_update_task}},
                        "id": "media_update_task",
                        "label": {"en": "Enable media update task", "fr": "Activer la tâche de mise à jour du média"},
                    },
                    {
                        "field": {"checkbox": {"value": _reconfigured_device.download_artwork}},
                        "id": "download_artwork",
                        "label": {
                            "en": "Download artwork instead of transmitting URL to the remote",
                            "fr": "Télécharger l'image au lieu de transmettre l'URL à la télécommande",
                        },
                    },
                    {
                        "field": {"checkbox": {"value": _reconfigured_device.disable_keyboard_map}},
                        "id": "disable_keyboard_map",
                        "label": {
                            "en": "Disable keyboard map : check only if some commands fail (eg arrow keys)",
                            "fr": "Désactiver les commandes clavier : cocher uniquement si certaines commandes"
                            " échouent (ex : commandes de direction)",
                        },
                    },
                ],
            )
        case "reset":
            config.devices.clear()  # triggers device instance removal
        case "backup_restore":
            return await _handle_backup_restore_step()
        case _:
            _LOG.error("Invalid configuration action: %s", action)
            return SetupError(error_type=IntegrationSetupError.OTHER)

    _setup_step = SetupSteps.DISCOVER
    return _user_input_manual


async def handle_discovery(_msg: UserDataResponse) -> RequestUserInput | SetupError:
    """
    Process user data response from the first setup process screen.

    If ``address`` field is set by the user: try connecting to device and retrieve device information.
    Otherwise, start Apple TV discovery and present the found devices to the user to choose from.

    :param _msg: response data from the requested user data
    :return: the setup action on how to continue
    """
    global _discovered_kodis
    global _setup_step

    dropdown_items = []

    _LOG.debug("Handle driver setup with discovery")
    # start discovery
    try:
        discovery = KodiDiscover()
        _discovered_kodis = await discovery.discover()
        _LOG.debug("Discovered Kodi devices : %s", _discovered_kodis)
    except Exception as ex:
        _LOG.error("Error during devices discovery %s", ex)
        return SetupError(error_type=IntegrationSetupError.NOT_FOUND)

    # only add new devices or configured devices requiring new pairing
    for discovered_kodi in _discovered_kodis:
        kodi_data = {"id": discovered_kodi["ip"], "label": {"en": f"Kodi {discovered_kodi['ip']}"}}
        existing = config.devices.get_by_id_or_address(discovered_kodi["id"], discovered_kodi["ip"])
        if _cfg_add_device and existing:
            _LOG.info("Skipping found device '%s': already configured", discovered_kodi["id"])
            continue
        dropdown_items.append(kodi_data)

    if not dropdown_items:
        _LOG.warning("No Kodi instance found")
        return SetupError(error_type=IntegrationSetupError.NOT_FOUND)

    _setup_step = SetupSteps.DEVICE_CHOICE
    # TODO #9 externalize language texts
    return RequestUserInput(
        {
            "en": "Please choose and configure your Kodi instance",
            "fr": "Sélectionnez et configurez votre instance Kodi",
        },
        [
            {
                "field": {"dropdown": {"value": dropdown_items[0]["id"], "items": dropdown_items}},
                "id": "choice",
                "label": {
                    "en": "Choose your Kodi instance",
                    "de": "Wähle deinen Kodi",
                    "fr": "Choisir votre instance Kodi",
                },
            },
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
                            "en": "Kodi must be running, and control enabled from Settings > "
                            "Services > Control section. Port numbers shouldn't be modified."
                            " Leave blank for automatic discovery.",
                            "fr": "Kodi doit être lancé et le contrôle activé depuis les "
                            "Paramètres > Services > Contrôle. Laisser les numéros des ports "
                            "inchangés.Laisser vide pour la découverte automatique.",
                        }
                    }
                },
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
            {
                "field": {"dropdown": {"value": KODI_DEFAULT_ARTWORK, "items": KODI_ARTWORK_LABELS}},
                "id": "artwork_type",
                "label": {
                    "en": "Artwork type to display",
                    "fr": "Type d'image média à afficher",
                },
            },
            {
                "field": {"dropdown": {"value": KODI_DEFAULT_TVSHOW_ARTWORK, "items": KODI_ARTWORK_TVSHOWS_LABELS}},
                "id": "artwork_type_tvshows",
                "label": {
                    "en": "Artwork type to display for TV Shows",
                    "fr": "Type d'image média à afficher pour les séries",
                },
            },
            {
                "field": {"checkbox": {"value": True}},
                "id": "media_update_task",
                "label": {"en": "Enable media update task", "fr": "Activer la tâche de mise à jour du média"},
            },
            {
                "field": {"checkbox": {"value": False}},
                "id": "download_artwork",
                "label": {
                    "en": "Download artwork instead of transmitting URL to the remote",
                    "fr": "Télécharger l'image au lieu de transmettre l'URL à la télécommande",
                },
            },
            {
                "field": {"checkbox": {"value": False}},
                "id": "disable_keyboard_map",
                "label": {
                    "en": "Disable keyboard map : check only if some commands fail (eg arrow keys)",
                    "fr": "Désactiver les commandes clavier : cocher uniquement si certaines commandes échouent "
                    "(ex : commandes de direction)",
                },
            },
        ],
    )


async def _handle_backup_restore_step() -> RequestUserInput:
    global _setup_step

    _setup_step = SetupSteps.BACKUP_RESTORE
    current_config = config.devices.export()

    _LOG.debug("Handle backup/restore step")

    return RequestUserInput(
        {
            "en": "Backup or restore devices configuration (all existing devices will be removed)",
            "fr": "Sauvegarder ou restaurer la configuration des appareils (tous les appareils existants seront supprimés)",
        },
        [
            {
                "field": {
                    "textarea": {
                        "value": current_config,
                    }
                },
                "id": "config",
                "label": {
                    "en": "Devices configuration",
                    "fr": "Configuration des appareils",
                },
            },
        ],
    )


async def _handle_configuration(msg: UserDataResponse) -> SetupComplete | SetupError:
    """
    Process user data response in a setup process.

    If ``address`` field is set by the user: try connecting to device and retrieve model information.
    Otherwise, start LG TV discovery and present the found devices to the user to choose from.

    :param msg: response data from the requested user data
    :return: the setup action on how to continue
    """
    # pylint: disable = W0602,W0718,R0915
    global _pairing_device
    global _pairing_device_ws
    global _setup_step
    global _discovered_kodis

    _LOG.debug("Handle configuration")

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
    address = msg.input_values.get("address", None)
    device_choice = msg.input_values.get("choice", None)
    port = msg.input_values["port"]
    ws_port = msg.input_values["ws_port"]
    username = msg.input_values["username"]
    password = msg.input_values["password"]
    ssl = msg.input_values["ssl"]
    artwork_type = msg.input_values.get("artwork_type", KODI_DEFAULT_ARTWORK)
    artwork_type_tvshows = msg.input_values.get("artwork_type_tvshows", KODI_DEFAULT_TVSHOW_ARTWORK)
    media_update_task = msg.input_values["media_update_task"]
    download_artwork = msg.input_values["download_artwork"]
    disable_keyboard_map = msg.input_values["disable_keyboard_map"]

    if ssl == "false":
        ssl = False
    else:
        ssl = True

    if media_update_task == "false":
        media_update_task = False
    else:
        media_update_task = True

    if download_artwork == "false":
        download_artwork = False
    else:
        download_artwork = True

    if disable_keyboard_map == "false":
        disable_keyboard_map = False
    else:
        disable_keyboard_map = True

    if device_choice:
        _LOG.debug("Configure device following discovery : %s %s", device_choice, _discovered_kodis)
        for discovered_kodi in _discovered_kodis:
            if device_choice == discovered_kodi["ip"]:
                address = discovered_kodi["ip"]

    _LOG.debug(
        "Starting driver setup for %s, port %s, websocket port %s, username %s, ssl %s",
        address,
        port,
        ws_port,
        username,
        ssl,
    )
    try:
        # simple connection check
        async with ClientSession(raise_for_status=True) as session:
            device = KodiHTTPConnection(
                host=address, port=port, username=username, password=password, timeout=5, session=session, ssl=ssl
            )
            kodi = Kodi(device)
            try:
                await kodi.ping()
                _LOG.debug("Connection %s:%s succeeded over HTTP", address, port)
            except CannotConnectError as ex:
                _LOG.warning("Cannot connect to %s:%s over HTTP [%s]", address, port, ex)
                return SetupError(error_type=IntegrationSetupError.CONNECTION_REFUSED)
            except InvalidAuthError:
                _LOG.warning("Authentication refused to %s:%s over HTTP", address, port)
                return SetupError(error_type=IntegrationSetupError.AUTHORIZATION_ERROR)
            device = KodiWSConnection(
                host=address,
                port=port,
                ws_port=ws_port,
                username=username,
                password=password,
                ssl=ssl,
                timeout=5,
                session=session,
            )
            try:
                await device.connect()
                if not device.connected:
                    _LOG.warning("Cannot connect to %s:%s over WebSocket", address, ws_port)
                    return SetupError(error_type=IntegrationSetupError.CONNECTION_REFUSED)
                kodi = Kodi(device)
                await kodi.ping()
                await device.close()
                _LOG.debug("Connection %s:%s succeeded over websocket", address, port)
            except CannotConnectError:
                _LOG.warning("Cannot connect to %s:%s over WebSocket", address, ws_port)
                return SetupError(error_type=IntegrationSetupError.CONNECTION_REFUSED)

            dropdown_items.append({"id": address, "label": {"en": f"Kodi [{address}]"}})
    except Exception as ex:
        _LOG.error("Cannot connect to manually entered address %s: %s", address, ex)
        return SetupError(error_type=IntegrationSetupError.CONNECTION_REFUSED)

    # TODO improve device ID (IP actually)
    config.devices.add(
        KodiConfigDevice(
            id=address,
            name="Kodi",
            address=address,
            username=username,
            password=password,
            port=port,
            ws_port=ws_port,
            ssl=ssl,
            artwork_type=artwork_type,
            artwork_type_tvshows=artwork_type_tvshows,
            media_update_task=media_update_task,
            download_artwork=download_artwork,
            disable_keyboard_map=disable_keyboard_map,
        )
    )  # triggers SonyLG TV instance creation
    config.devices.store()

    await asyncio.sleep(1)
    _LOG.info("Setup successfully completed for %s", address)
    return SetupComplete()


async def _handle_device_reconfigure(msg: UserDataResponse) -> SetupComplete | SetupError:
    """
    Process reconfiguration of a registered Android TV device.

    :param msg: response data from the requested user data
    :return: the setup action on how to continue: SetupComplete after updating configuration
    """
    # flake8: noqa:F824
    # pylint: disable=W0602
    global _reconfigured_device

    _LOG.debug("Handle device reconfigure")

    if _reconfigured_device is None:
        return SetupError()

    address = msg.input_values["address"]
    port = msg.input_values["port"]
    ws_port = msg.input_values["ws_port"]
    username = msg.input_values["username"]
    password = msg.input_values["password"]
    ssl = msg.input_values["ssl"]
    artwork_type = msg.input_values.get("artwork_type", KODI_DEFAULT_ARTWORK)
    artwork_type_tvshows = msg.input_values.get("artwork_type_tvshows", KODI_DEFAULT_TVSHOW_ARTWORK)
    media_update_task = msg.input_values["media_update_task"]
    download_artwork = msg.input_values["download_artwork"]
    disable_keyboard_map = msg.input_values["disable_keyboard_map"]

    if ssl == "false":
        ssl = False
    else:
        ssl = True

    if media_update_task == "false":
        media_update_task = False
    else:
        media_update_task = True

    if download_artwork == "false":
        download_artwork = False
    else:
        download_artwork = True

    if disable_keyboard_map == "false":
        disable_keyboard_map = False
    else:
        disable_keyboard_map = True

    _LOG.debug("User has changed configuration")
    _reconfigured_device.address = address
    _reconfigured_device.username = username
    _reconfigured_device.password = password
    _reconfigured_device.port = port
    _reconfigured_device.ws_port = ws_port
    _reconfigured_device.ssl = ssl
    _reconfigured_device.artwork_type = artwork_type
    _reconfigured_device.artwork_type_tvshows = artwork_type_tvshows
    _reconfigured_device.media_update_task = media_update_task
    _reconfigured_device.download_artwork = download_artwork
    _reconfigured_device.disable_keyboard_map = disable_keyboard_map

    config.devices.add_or_update(_reconfigured_device)  # triggers ATV instance update
    await asyncio.sleep(1)
    _LOG.info("Setup successfully completed for %s", _reconfigured_device.name)

    return SetupComplete()


async def _handle_backup_restore(msg: UserDataResponse) -> SetupComplete | SetupError:
    """
    Process import of configuration

    :param msg: response data from the requested user data
    :return: the setup action on how to continue: SetupComplete after updating configuration
    """
    # flake8: noqa:F824
    # pylint: disable=W0602
    global _reconfigured_device

    _LOG.debug("Handle backup/restore")
    updated_config = msg.input_values["config"]
    _LOG.info("Replacing configuration with : %s", updated_config)
    res = config.devices.import_config(updated_config)
    if res == ConfigImportResult.ERROR:
        _LOG.error("Setup error, unable to import updated configuration : %s", updated_config)
        return SetupError(error_type=IntegrationSetupError.OTHER)
    elif res == ConfigImportResult.WARNINGS:
        _LOG.error("Setup warning, configuration imported with warnings : %s", config.devices)
    _LOG.debug("Configuration imported successfully")

    await asyncio.sleep(1)
    return SetupComplete()
