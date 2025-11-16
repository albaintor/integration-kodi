"""
Media-player entity functions.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
from asyncio import shield
from typing import Any

from ucapi import EntityTypes, Remote, StatusCodes
from ucapi.media_player import States as MediaStates
from ucapi.remote import Attributes, Commands, Features
from ucapi.remote import States as RemoteStates

import kodi
from config import KodiConfigDevice, create_entity_id
from const import (
    KODI_REMOTE_BUTTONS_MAPPING,
    KODI_REMOTE_SIMPLE_COMMANDS,
    KODI_REMOTE_UI_PAGES,
    key_update_helper,
)
from media_player import KodiMediaPlayer

_LOG = logging.getLogger(__name__)

# TODO to improve : the media states are calculated for media player entity,
#  then they have to be converted to remote states
# A device state map should be defined and then mapped to both entity types
KODI_REMOTE_STATE_MAPPING = {
    MediaStates.OFF: RemoteStates.OFF,
    MediaStates.ON: RemoteStates.ON,
    MediaStates.STANDBY: RemoteStates.ON,
    MediaStates.PLAYING: RemoteStates.ON,
    MediaStates.PAUSED: RemoteStates.ON,
}

COMMAND_TIMEOUT = 4.5


def get_int_param(param: str, params: dict[str, Any], default: int):
    """Get parameter in integer format."""
    # TODO bug to be fixed on UC Core : some params are sent as (empty) strings by remote (hold == "")
    value = params.get(param, default)
    if isinstance(value, str) and value == "":
        return default
    if isinstance(value, str) and len(value) > 0:
        return int(float(value))
    return value


class KodiRemote(Remote):
    """Representation of a Kodi Media Player entity."""

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        # pylint: disable = R0801
        self._device: kodi.KodiDevice = device
        _LOG.debug("KodiRemote init")
        entity_id = create_entity_id(config_device.id, EntityTypes.REMOTE)
        features = [Features.SEND_CMD, Features.ON_OFF]
        attributes = {
            Attributes.STATE: KODI_REMOTE_STATE_MAPPING.get(device.get_state()),
        }
        KODI_REMOTE_SIMPLE_COMMANDS.sort()
        super().__init__(
            entity_id,
            config_device.name,
            features,
            attributes,
            simple_commands=KODI_REMOTE_SIMPLE_COMMANDS,
            button_mapping=KODI_REMOTE_BUTTONS_MAPPING,
            ui_pages=KODI_REMOTE_UI_PAGES,
        )

    async def command(self, cmd_id: str, params: dict[str, Any] | None = None) -> StatusCodes:
        """
        Media-player entity command handler.

        Called by the integration-API if a command is sent to a configured media-player entity.

        :param cmd_id: command
        :param params: optional command parameters
        :return: status code of the command request
        """
        _LOG.info("Got %s command request: %s %s", self.id, cmd_id, params)

        if self._device is None:
            _LOG.warning("No Kodi instance for entity: %s", self.id)
            return StatusCodes.SERVICE_UNAVAILABLE

        # Occurs when the user press a button after wake up from standby and
        # the driver reconnection is not triggered yet
        if not self._device.kodi_connection or not self._device.kodi_connection.connected:
            await self._device.connect()

        res = StatusCodes.OK
        if cmd_id == Commands.ON:
            res = await self._device.power_on()
        elif cmd_id == Commands.OFF:
            res = await self._device.power_off()
        elif cmd_id == Commands.TOGGLE:
            if self._device.available:
                res = await self._device.power_off()
            else:
                res = await self._device.power_on()
        elif cmd_id in [Commands.SEND_CMD, Commands.SEND_CMD_SEQUENCE]:
            # If the duration exceeds the remote timeout, keep it running and return immediately
            try:
                async with asyncio.timeout(COMMAND_TIMEOUT):
                    res = await shield(self.send_commands(cmd_id, params))
            except asyncio.TimeoutError:
                _LOG.info("[%s] Command request timeout, keep running: %s %s", self.id, cmd_id, params)
        else:
            return StatusCodes.NOT_IMPLEMENTED
        return res

    async def send_commands(self, cmd_id: str, params: dict[str, Any] | None = None) -> StatusCodes:
        """Handle custom command or commands sequence."""
        hold = get_int_param("hold", params, 0)
        delay = get_int_param("delay", params, 0)
        repeat = get_int_param("repeat", params, 1)
        command = params.get("command", "")
        res = StatusCodes.OK
        for _i in range(0, repeat):
            if cmd_id == Commands.SEND_CMD:
                result = await KodiMediaPlayer.mediaplayer_command(self.id, self._device, command, params)
                if result == StatusCodes.NOT_IMPLEMENTED:
                    result = await self._device.command_button({"button": command, "keymap": "KB", "holdtime": hold})
                if result != StatusCodes.OK:
                    res = result
                if delay > 0:
                    await asyncio.sleep(delay / 1000)
            else:
                commands = params.get("sequence", [])
                for command in commands:
                    result = KodiMediaPlayer.mediaplayer_command(self.id, self._device, command, params)
                    if result == StatusCodes.NOT_IMPLEMENTED:
                        result = await self._device.command_button(
                            {"button": command, "keymap": "KB", "holdtime": hold}
                        )
                    if result != StatusCodes.OK:
                        res = result
                    if delay > 0:
                        await asyncio.sleep(delay / 1000)
        return res

    def filter_changed_attributes(self, update: dict[str, Any]) -> dict[str, Any]:
        """
        Filter the given attributes and return only the changed values.

        :param update: dictionary with attributes.
        :return: filtered entity attributes containing changed attributes only.
        """
        attributes = {}

        if Attributes.STATE in update:
            state = KODI_REMOTE_STATE_MAPPING.get(update[Attributes.STATE])
            attributes = key_update_helper(self.attributes, Attributes.STATE, state, attributes)

        _LOG.debug("KodiRemote update attributes %s", attributes)
        return attributes
