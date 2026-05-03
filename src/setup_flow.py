"""
Setup flow for LG TV integration.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import copy
import logging
from enum import IntEnum
from typing import Any

from aiohttp import ClientSession
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

import config
from config import ConfigImportResult, KodiConfigDevice
from const import (
    KODI_DEFAULT_NAME,
    KODI_POWEROFF_COMMANDS,
    KodiStreamConfig,
)
from discover import KodiDiscover
from pykodi.kodi import (
    CannotConnectError,
    InvalidAuthError,
    Kodi,
    KodiConnection,
    KodiHTTPConnection,
    KodiWSConnection,
)
from setup_fields import KODI_DEFAULT_ARTWORK, KODI_DEFAULT_TVSHOW_ARTWORK, SETUP_FIELDS

_LOG = logging.getLogger(__name__)


# pylint: disable = C0301,W1405,C0302,C0103
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


def set_setup_field(fields: list[dict[str, Any]], field_id: str, value: Any):
    """Set field value from field id."""
    for field in fields:
        if field.get("id") == field_id and (field_entry := field.get("field")):
            if isinstance(field_entry, dict):
                for val in field_entry.values():
                    if isinstance(val, dict):
                        val["value"] = value


class SetupFlow:
    """Setup flow."""

    def __init__(self):
        self._setup_step = SetupSteps.INIT
        self._cfg_add_device: bool = False
        self._discovered_kodis: list[dict[str, str]] = []
        self._pairing_device: KodiConnection | None = None
        self._pairing_device_ws: KodiWSConnection | None = None
        self._reconfigured_device: KodiConfigDevice | None = None

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
            *copy.deepcopy(SETUP_FIELDS),
        ],
    )

    # pylint: disable=R0911
    async def driver_setup_handler(self, msg: SetupDriver) -> SetupAction:
        """
        Dispatch driver setup requests to corresponding handlers.

        Either start the setup process or handle the selected LG TV device.

        :param msg: the setup driver request object, either DriverSetupRequest or UserDataResponse
        :return: the setup action on how to continue
        """

        if isinstance(msg, DriverSetupRequest):
            self._setup_step = SetupSteps.INIT
            self._cfg_add_device = False
            return await self.handle_driver_setup(msg)

        if isinstance(msg, UserDataResponse):
            _LOG.debug("Setup handler message : step %s, message : %s", self._setup_step, msg)
            manual_config = False
            if self._setup_step == SetupSteps.WORKFLOW_MODE:
                if msg.input_values.get("configuration_mode", "") == "normal":
                    self._setup_step = SetupSteps.DEVICE_CONFIGURATION_MODE
                    _LOG.debug("Starting normal setup workflow")
                    return self._user_input_manual
                _LOG.debug("User requested backup/restore of configuration")
                return await self._handle_backup_restore_step()
            if "address" in msg.input_values and len(msg.input_values["address"]) > 0:
                manual_config = True
            if self._setup_step == SetupSteps.DEVICE_CONFIGURATION_MODE:
                if "action" in msg.input_values:
                    _LOG.debug("Setup flow starts with existing configuration")
                    return await self.handle_configuration_mode(msg)
                if not manual_config:
                    _LOG.debug("Setup flow in discovery mode")
                    self._setup_step = SetupSteps.DISCOVER
                    return await self.handle_discovery(msg)
                _LOG.debug("Setup flow configuration mode")
                return await self._handle_configuration(msg)
            # When user types an address at start (manual configuration)
            if self._setup_step == SetupSteps.DISCOVER and manual_config:
                return await self._handle_configuration(msg)
            # No address typed, discovery mode then
            if self._setup_step == SetupSteps.DISCOVER:
                return await self.handle_discovery(msg)
            if self._setup_step == SetupSteps.RECONFIGURE:
                return await self._handle_device_reconfigure(msg)
            if self._setup_step == SetupSteps.DEVICE_CHOICE and "choice" in msg.input_values:
                return await self._handle_configuration(msg)
            if self._setup_step == SetupSteps.BACKUP_RESTORE:
                return await self._handle_backup_restore(msg)
            _LOG.error("No or invalid user response was received: %s (step %s)", msg, self._setup_step)
        elif isinstance(msg, AbortDriverSetup):
            _LOG.info("Setup was aborted with code: %s", msg.error)
            # pylint: disable = W0718
            if self._pairing_device:
                try:
                    await self._pairing_device.close()
                except Exception:
                    pass
                self._pairing_device = None
            if self._pairing_device_ws:
                try:
                    await self._pairing_device_ws.close()
                except Exception:
                    pass
                self._pairing_device_ws = None
            self._setup_step = SetupSteps.INIT

        return SetupError()

    async def handle_driver_setup(self, msg: DriverSetupRequest) -> RequestUserInput | SetupError:
        """
        Start driver setup.

        Initiated by Remote Two to set up the driver.
        Ask user to enter ip-address for manual configuration, otherwise auto-discovery is used.

        :param msg: not used, we don't have any input fields in the first setup screen.
        :return: the setup action on how to continue
        """

        # workaround for web-configurator not picking up first response
        await asyncio.sleep(1)

        reconfigure = msg.reconfigure
        _LOG.debug("Handle driver setup, reconfigure=%s", reconfigure)
        if reconfigure:
            self._setup_step = SetupSteps.DEVICE_CONFIGURATION_MODE

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

        # Initial setup, make sure we have a clean configuration
        config.devices.clear()  # triggers device instance removal
        self._setup_step = SetupSteps.WORKFLOW_MODE
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

    async def handle_configuration_mode(self, msg: UserDataResponse) -> RequestUserInput | SetupComplete | SetupError:
        """
        Process user data response in a setup process.

        If ``address`` field is set by the user: try connecting to device and retrieve model information.
        Otherwise, start instances discovery and present the found devices to the user to choose from.

        :param msg: response data from the requested user data
        :return: the setup action on how to continue
        """
        action = msg.input_values["action"]

        _LOG.debug("Handle configuration mode")

        # workaround for web-configurator not picking up first response
        await asyncio.sleep(1)

        match action:
            case "add":
                self._cfg_add_device = True
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

                self._setup_step = SetupSteps.RECONFIGURE
                self._reconfigured_device = selected_device

                try:
                    user_input = RequestUserInput(
                        {
                            "en": "Configure your Kodi device",
                            "fr": "Configurez votre appareil Kodi",
                        },
                        [
                            {
                                "field": {"text": {"value": self._reconfigured_device.address}},
                                "id": "address",
                                "label": {"en": "IP address", "de": "IP-Adresse", "fr": "Adresse IP"},
                            },
                            {
                                "field": {"text": {"value": self._reconfigured_device.name}},
                                "id": "name",
                                "label": {"en": "Device name", "fr": "Nom de l'appareil"},
                            },
                            *copy.deepcopy(SETUP_FIELDS),
                        ],
                    )
                    _LOG.debug("INPUT CONFIG %s", user_input)
                    set_setup_field(user_input.settings, "username", self._reconfigured_device.username)
                    set_setup_field(user_input.settings, "password", self._reconfigured_device.password)
                    set_setup_field(user_input.settings, "ws_port", str(self._reconfigured_device.ws_port))
                    set_setup_field(user_input.settings, "port", self._reconfigured_device.port)
                    set_setup_field(user_input.settings, "ssl", self._reconfigured_device.ssl)
                    set_setup_field(user_input.settings, "artwork_type", self._reconfigured_device.artwork_type)
                    set_setup_field(
                        user_input.settings, "artwork_type_tvshows", self._reconfigured_device.artwork_type_tvshows
                    )
                    set_setup_field(
                        user_input.settings, "browse_media_root", self._reconfigured_device.browse_media_root
                    )
                    set_setup_field(
                        user_input.settings, "favorites_in_root", self._reconfigured_device.favorites_in_root
                    )
                    set_setup_field(
                        user_input.settings, "show_channel_groups", self._reconfigured_device.show_channel_groups
                    )
                    set_setup_field(
                        user_input.settings, "browsing_video_sort", self._reconfigured_device.browsing_video_sort
                    )
                    set_setup_field(
                        user_input.settings, "browsing_album_sort", self._reconfigured_device.browsing_album_sort
                    )
                    set_setup_field(
                        user_input.settings, "browsing_files_sort", self._reconfigured_device.browsing_files_sort
                    )
                    set_setup_field(user_input.settings, "show_stream_name", self._reconfigured_device.show_stream_name)
                    set_setup_field(
                        user_input.settings,
                        "show_stream_language_name",
                        self._reconfigured_device.show_stream_language_name,
                    )
                    set_setup_field(
                        user_input.settings, "media_update_task", self._reconfigured_device.media_update_task
                    )
                    set_setup_field(user_input.settings, "download_artwork", self._reconfigured_device.download_artwork)
                    set_setup_field(
                        user_input.settings, "disable_keyboard_map", self._reconfigured_device.disable_keyboard_map
                    )
                    set_setup_field(
                        user_input.settings,
                        "sensor_audio_stream_config",
                        self._reconfigured_device.sensor_audio_stream_config,
                    )
                    set_setup_field(
                        user_input.settings,
                        "sensor_subtitle_stream_config",
                        self._reconfigured_device.sensor_subtitle_stream_config,
                    )
                    set_setup_field(
                        user_input.settings,
                        "sensor_include_device_name",
                        self._reconfigured_device.sensor_include_device_name,
                    )
                    set_setup_field(
                        user_input.settings, "power_off_command", self._reconfigured_device.power_off_command
                    )
                    return user_input
                except Exception as ex:  # pylint: disable=W0718
                    _LOG.exception("Invalid configuration: %s", ex)
                    return SetupError(error_type=IntegrationSetupError.OTHER)
            case "reset":
                config.devices.clear()  # triggers device instance removal
            case "backup_restore":
                return await self._handle_backup_restore_step()
            case _:
                _LOG.error("Invalid configuration action: %s", action)
                return SetupError(error_type=IntegrationSetupError.OTHER)

        self._setup_step = SetupSteps.DISCOVER
        return self._user_input_manual

    async def handle_discovery(self, _msg: UserDataResponse) -> RequestUserInput | SetupError:
        """
        Process user data response from the first setup process screen.

        If ``address`` field is set by the user: try connecting to device and retrieve device information.
        Otherwise, start Apple TV discovery and present the found devices to the user to choose from.

        :param _msg: response data from the requested user data
        :return: the setup action on how to continue
        """

        dropdown_items = []

        _LOG.debug("Handle driver setup with discovery")
        # start discovery
        try:
            discovery = KodiDiscover()
            self._discovered_kodis = await discovery.discover()
            _LOG.debug("Discovered Kodi devices : %s", self._discovered_kodis)
        # pylint: disable = W0718
        except Exception as ex:
            _LOG.error("Error during devices discovery %s", ex)
            return SetupError(error_type=IntegrationSetupError.NOT_FOUND)

        # only add new devices or configured devices requiring new pairing
        for discovered_kodi in self._discovered_kodis:
            kodi_data = {"id": discovered_kodi["ip"], "label": {"en": f"Kodi {discovered_kodi['ip']}"}}
            existing = config.devices.get_by_id_or_address(discovered_kodi["id"], discovered_kodi["ip"])
            if self._cfg_add_device and existing:
                _LOG.info("Skipping found device '%s': already configured", discovered_kodi["id"])
                continue
            dropdown_items.append(kodi_data)

        if not dropdown_items:
            _LOG.warning("No Kodi instance found")
            return SetupError(error_type=IntegrationSetupError.NOT_FOUND)

        self._setup_step = SetupSteps.DEVICE_CHOICE
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
                *copy.deepcopy(SETUP_FIELDS),
            ],
        )

    async def _handle_backup_restore_step(self) -> RequestUserInput:
        self._setup_step = SetupSteps.BACKUP_RESTORE
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

    async def _handle_configuration(self, msg: UserDataResponse) -> SetupComplete | SetupError:
        """
        Process user data response in a setup process.

        If ``address`` field is set by the user: try connecting to device and retrieve model information.
        Otherwise, start LG TV discovery and present the found devices to the user to choose from.

        :param msg: response data from the requested user data
        :return: the setup action on how to continue
        """
        # pylint: disable=W0602,W0718,R0915,R0914
        _LOG.debug("Handle configuration")

        # clear all configured devices and any previous pairing attempt
        if self._pairing_device:
            try:
                await self._pairing_device.close()
            except Exception:
                pass
            self._pairing_device = None
        if self._pairing_device_ws:
            try:
                await self._pairing_device_ws.close()
            except Exception:
                pass
            self._pairing_device_ws = None

        dropdown_items = []
        address = msg.input_values.get("address", None)
        device_choice = msg.input_values.get("choice", None)
        port = msg.input_values["port"]
        ws_port = msg.input_values["ws_port"]
        username = msg.input_values["username"]
        password = msg.input_values["password"]
        ssl = msg.input_values.get("ssl", "false") == "true"
        browsing_video_sort = msg.input_values.get("browsing_video_sort", "")
        browsing_album_sort = msg.input_values.get("browsing_album_sort", "")
        browsing_files_sort = msg.input_values.get("browsing_files_sort", "")
        artwork_type = msg.input_values.get("artwork_type", KODI_DEFAULT_ARTWORK)
        artwork_type_tvshows = msg.input_values.get("artwork_type_tvshows", KODI_DEFAULT_TVSHOW_ARTWORK)
        media_update_task = msg.input_values.get("media_update_task", "false") == "true"
        download_artwork = msg.input_values.get("download_artwork", "false") == "true"
        disable_keyboard_map = msg.input_values.get("disable_keyboard_map", "false") == "true"
        show_stream_name = msg.input_values.get("show_stream_name", "false") == "true"
        show_stream_language_name = msg.input_values.get("show_stream_language_name", "false") == "true"
        sensor_include_device_name = msg.input_values.get("sensor_include_device_name", "false") == "true"
        power_off_command = msg.input_values.get("power_off_command", next(iter(KODI_POWEROFF_COMMANDS)))
        browse_media_root = msg.input_values.get("browse_media_root", "")
        favorites_in_root = msg.input_values.get("favorites_in_root", "false") == "true"
        show_channel_groups = msg.input_values.get("show_channel_groups", "true") == "true"

        try:
            sensor_audio_stream_config = int(
                msg.input_values.get("sensor_audio_stream_config", f"{int(KodiStreamConfig.FULL)}")
            )
        except ValueError:
            sensor_audio_stream_config = int(KodiStreamConfig.STREAM_NAME)
        try:
            sensor_subtitle_stream_config = int(
                msg.input_values.get("sensor_subtitle_stream_config", f"{int(KodiStreamConfig.FULL)}")
            )
        except ValueError:
            sensor_subtitle_stream_config = int(KodiStreamConfig.STREAM_NAME)

        if device_choice:
            _LOG.debug("Configure device following discovery : %s %s", device_choice, self._discovered_kodis)
            for discovered_kodi in self._discovered_kodis:
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
                    name = await kodi.get_name()
                    if name == KODI_DEFAULT_NAME:
                        name = f"Kodi {address}"

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
                name=name,
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
                show_stream_name=show_stream_name,
                show_stream_language_name=show_stream_language_name,
                sensor_audio_stream_config=sensor_audio_stream_config,
                sensor_subtitle_stream_config=sensor_subtitle_stream_config,
                sensor_include_device_name=sensor_include_device_name,
                power_off_command=power_off_command,
                browsing_video_sort=browsing_video_sort,
                browsing_album_sort=browsing_album_sort,
                browsing_files_sort=browsing_files_sort,
                browse_media_root=browse_media_root,
                favorites_in_root=favorites_in_root,
                show_channel_groups=show_channel_groups,
            )
        )  # triggers SonyLG TV instance creation
        config.devices.store()

        await asyncio.sleep(1)
        _LOG.info("Setup successfully completed for %s", address)
        return SetupComplete()

    async def _handle_device_reconfigure(self, msg: UserDataResponse) -> SetupComplete | SetupError:
        """
        Process reconfiguration of a registered Android TV device.

        :param msg: response data from the requested user data
        :return: the setup action on how to continue: SetupComplete after updating configuration
        """
        # flake8: noqa:F824
        # pylint: disable=W0602, R0915, R0914

        _LOG.debug("Handle device reconfigure")

        if self._reconfigured_device is None:
            return SetupError()

        address = msg.input_values["address"]
        port = msg.input_values["port"]
        ws_port = msg.input_values["ws_port"]
        username = msg.input_values["username"]
        password = msg.input_values["password"]
        ssl = msg.input_values.get("ssl", "false") == "true"
        artwork_type = msg.input_values.get("artwork_type", KODI_DEFAULT_ARTWORK)
        artwork_type_tvshows = msg.input_values.get("artwork_type_tvshows", KODI_DEFAULT_TVSHOW_ARTWORK)
        browsing_video_sort = msg.input_values.get("browsing_video_sort", "")
        browsing_album_sort = msg.input_values.get("browsing_album_sort", "")
        browsing_files_sort = msg.input_values.get("browsing_files_sort", "")
        media_update_task = msg.input_values.get("media_update_task", "false") == "true"
        download_artwork = msg.input_values.get("download_artwork", "false") == "true"
        disable_keyboard_map = msg.input_values.get("disable_keyboard_map", "false") == "true"
        show_stream_name = msg.input_values.get("show_stream_name", "false") == "true"
        show_stream_language_name = msg.input_values.get("show_stream_language_name", "false") == "true"
        sensor_include_device_name = msg.input_values.get("sensor_include_device_name", "false") == "true"
        power_off_command = msg.input_values.get("power_off_command", next(iter(KODI_POWEROFF_COMMANDS)))
        browse_media_root = msg.input_values.get("browse_media_root", "")
        favorites_in_root = msg.input_values.get("favorites_in_root", "false") == "true"
        show_channel_groups = msg.input_values.get("show_channel_groups", "true") == "true"
        name = msg.input_values["name"]
        try:
            sensor_audio_stream_config = int(
                msg.input_values.get("sensor_audio_stream_config", f"{KodiStreamConfig.FULL}")
            )
        except ValueError:
            sensor_audio_stream_config = int(KodiStreamConfig.FULL)
        try:
            sensor_subtitle_stream_config = int(
                msg.input_values.get("sensor_subtitle_stream_config", f"{KodiStreamConfig.FULL}")
            )
        except ValueError:
            sensor_subtitle_stream_config = int(KodiStreamConfig.FULL)

        _LOG.debug("User has changed configuration")
        self._reconfigured_device.address = address
        self._reconfigured_device.name = name
        self._reconfigured_device.username = username
        self._reconfigured_device.password = password
        self._reconfigured_device.port = port
        self._reconfigured_device.ws_port = ws_port
        self._reconfigured_device.ssl = ssl
        self._reconfigured_device.artwork_type = artwork_type
        self._reconfigured_device.artwork_type_tvshows = artwork_type_tvshows
        self._reconfigured_device.media_update_task = media_update_task
        self._reconfigured_device.download_artwork = download_artwork
        self._reconfigured_device.disable_keyboard_map = disable_keyboard_map
        self._reconfigured_device.show_stream_name = show_stream_name
        self._reconfigured_device.show_stream_language_name = show_stream_language_name
        self._reconfigured_device.sensor_audio_stream_config = sensor_audio_stream_config
        self._reconfigured_device.sensor_subtitle_stream_config = sensor_subtitle_stream_config
        self._reconfigured_device.sensor_include_device_name = sensor_include_device_name
        self._reconfigured_device.power_off_command = power_off_command
        self._reconfigured_device.browsing_video_sort = browsing_video_sort
        self._reconfigured_device.browsing_album_sort = browsing_album_sort
        self._reconfigured_device.browsing_files_sort = browsing_files_sort
        self._reconfigured_device.browse_media_root = browse_media_root
        self._reconfigured_device.favorites_in_root = favorites_in_root
        self._reconfigured_device.show_channel_groups = show_channel_groups

        config.devices.add_or_update(self._reconfigured_device)  # triggers ATV instance update
        await asyncio.sleep(1)
        _LOG.info("Setup successfully completed for %s", self._reconfigured_device.name)

        return SetupComplete()

    async def _handle_backup_restore(self, msg: UserDataResponse) -> SetupComplete | SetupError:
        """
        Process import of configuration

        :param msg: response data from the requested user data
        :return: the setup action on how to continue: SetupComplete after updating configuration
        """
        # flake8: noqa:F824
        # pylint: disable=W0602
        _LOG.debug("Handle backup/restore")
        updated_config = msg.input_values["config"]
        _LOG.info("Replacing configuration with : %s", updated_config)
        res = config.devices.import_config(updated_config)
        if res == ConfigImportResult.ERROR:
            _LOG.error("Setup error, unable to import updated configuration : %s", updated_config)
            return SetupError(error_type=IntegrationSetupError.OTHER)
        if res == ConfigImportResult.WARNINGS:
            _LOG.error("Setup warning, configuration imported with warnings : %s", config.devices)
        _LOG.debug("Configuration imported successfully")

        await asyncio.sleep(1)
        return SetupComplete()
