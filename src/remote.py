"""
Media-player entity functions.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
from typing import Any

import kodi
from config import KodiConfigDevice, create_entity_id
from const import (
    KODI_ACTIONS_KEYMAP,
    KODI_BUTTONS_KEYMAP,
    KODI_REMOTE_BUTTONS_MAPPING,
    KODI_REMOTE_SIMPLE_COMMANDS,
    KODI_REMOTE_UI_PAGES,
    KODI_SIMPLE_COMMANDS,
    key_update_helper,
    KODI_SIMPLE_COMMANDS_DIRECT, KODI_ALTERNATIVE_BUTTONS_KEYMAP,
)
from ucapi import EntityTypes, Remote, StatusCodes
from ucapi.media_player import Commands as MediaPlayerCommands
from ucapi.media_player import States as MediaStates
from ucapi.remote import Attributes, Commands, Features, Options
from ucapi.remote import States as RemoteStates

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
        super().__init__(
            entity_id,
            config_device.name,
            features,
            attributes,
            simple_commands=KODI_REMOTE_SIMPLE_COMMANDS,
            button_mapping=KODI_REMOTE_BUTTONS_MAPPING,
            ui_pages=KODI_REMOTE_UI_PAGES,
        )

    def get_int_param(self, param: str, params: dict[str, Any], default: int):
        """Get parameter in integer format."""
        # TODO bug to be fixed on UC Core : some params are sent as (empty) strings by remote (hold == "")
        value = params.get(param, default)
        if isinstance(value, str) and len(value) > 0:
            return int(float(value))
        return default

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

        repeat = self.get_int_param("repeat", params, 1)
        res = StatusCodes.OK
        for _i in range(0, repeat):
            res = await self.handle_command(cmd_id, params)
        return res

    async def handle_command(self, cmd_id: str, params: dict[str, Any] | None = None) -> StatusCodes:
        """Handle command."""
        hold = self.get_int_param("hold", params, 0)
        delay = self.get_int_param("delay", params, 0)
        command = params.get("command", "")

        if command == MediaPlayerCommands.VOLUME:
            res = await self._device.set_volume_level(params.get("volume"))
        elif command == MediaPlayerCommands.VOLUME_UP:
            res = await self._device.volume_up()
        elif command == MediaPlayerCommands.VOLUME_DOWN:
            res = await self._device.volume_down()
        elif command == MediaPlayerCommands.MUTE_TOGGLE:
            res = await self._device.mute(not self._device.is_volume_muted)
        elif command == MediaPlayerCommands.MUTE:
            res = await self._device.mute(True)
        elif command == MediaPlayerCommands.UNMUTE:
            res = await self._device.mute(False)
        elif command == MediaPlayerCommands.ON:
            res = await self._device.power_on()
        elif command == MediaPlayerCommands.OFF:
            res = await self._device.power_off()
        elif command == MediaPlayerCommands.NEXT:
            res = await self._device.next()
        elif command == MediaPlayerCommands.PREVIOUS:
            res = await self._device.previous()
        elif command == MediaPlayerCommands.PLAY_PAUSE:
            res = await self._device.play_pause()
        elif command == MediaPlayerCommands.STOP:
            res = await self._device.stop()
        elif command == MediaPlayerCommands.HOME:
            res = await self._device.home()
        elif command == MediaPlayerCommands.SETTINGS:
            return StatusCodes.NOT_IMPLEMENTED  # TODO ?
        elif command == MediaPlayerCommands.CONTEXT_MENU:
            res = await self._device.context_menu()
        elif not self._device.device_config.disable_keyboard_map and cmd_id in KODI_BUTTONS_KEYMAP:
            res = await self._device.command_button(KODI_BUTTONS_KEYMAP[cmd_id])
        elif self._device.device_config.disable_keyboard_map and cmd_id in KODI_ALTERNATIVE_BUTTONS_KEYMAP:
            command = KODI_ALTERNATIVE_BUTTONS_KEYMAP[cmd_id]
            res = await self._device.call_command(command["method"], **command["params"])
        elif command in KODI_ACTIONS_KEYMAP:
            res = await self._device.command_action(KODI_ACTIONS_KEYMAP[command])
        elif command in self.options[Options.SIMPLE_COMMANDS]:
            target_command = KODI_SIMPLE_COMMANDS[cmd_id]
            if target_command in KODI_SIMPLE_COMMANDS_DIRECT:
                res = await self._device.call_command(target_command)
            else:
                res = await self._device.command_action(target_command)
        elif cmd_id == Commands.SEND_CMD:
            res = await self._device.command_button({"button": command, "keymap": "KB", "holdtime": hold})
        elif cmd_id == Commands.SEND_CMD_SEQUENCE:
            commands = params.get("sequence", [])  # .split(",")
            res = StatusCodes.OK
            for command in commands:
                res = await self.handle_command(Commands.SEND_CMD, {"command": command, "params": params})
                if delay > 0:
                    await asyncio.sleep(delay)
        else:
            return StatusCodes.NOT_IMPLEMENTED
        if delay > 0 and cmd_id != Commands.SEND_CMD_SEQUENCE:
            await asyncio.sleep(delay)
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
