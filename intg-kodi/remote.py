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
from ucapi import EntityTypes, Remote, StatusCodes
from ucapi.media_player import Commands as MediaPlayerCommands, States as MediaStates
from ucapi.remote import Attributes, Commands, States as RemoteStates, Options, Features
from const import KODI_SIMPLE_COMMANDS, KODI_ACTIONS_KEYMAP, KODI_BUTTONS_KEYMAP, KODI_REMOTE_BUTTONS_MAPPING, \
    KODI_REMOTE_UI_PAGES, KODI_REMOTE_SIMPLE_COMMANDS

_LOG = logging.getLogger(__name__)

KODI_REMOTE_STATE_MAPPING = {
    MediaStates.OFF: RemoteStates.OFF,
    MediaStates.ON: RemoteStates.ON,
    MediaStates.STANDBY: RemoteStates.ON,
    MediaStates.PLAYING: RemoteStates.ON,
    MediaStates.PAUSED: RemoteStates.ON
}

class KodiRemote(Remote):
    """Representation of a Kodi Media Player entity."""

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        self._device: kodi.KodiDevice = device
        _LOG.debug("KodiRemote init")
        entity_id = create_entity_id(config_device.id, EntityTypes.REMOTE)
        features = [Features.SEND_CMD]
        attributes = {
            Attributes.STATE: KODI_REMOTE_STATE_MAPPING.get(kodi.KODI_STATE_MAPPING.get(device.state)),
        }
        super().__init__(
            entity_id,
            config_device.name,
            features,
            attributes,
            simple_commands=KODI_REMOTE_SIMPLE_COMMANDS,
            button_mapping=KODI_REMOTE_BUTTONS_MAPPING,
            ui_pages=KODI_REMOTE_UI_PAGES
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

        if cmd_id == MediaPlayerCommands.VOLUME:
            res = await self._device.set_volume_level(params.get("volume"))
        elif cmd_id == MediaPlayerCommands.VOLUME_UP:
            res = await self._device.volume_up()
        elif cmd_id == MediaPlayerCommands.VOLUME_DOWN:
            res = await self._device.volume_down()
        elif cmd_id == MediaPlayerCommands.MUTE_TOGGLE:
            res = await self._device.mute(not self._device.is_volume_muted)
        elif cmd_id == MediaPlayerCommands.MUTE:
            res = await self._device.mute(True)
        elif cmd_id == MediaPlayerCommands.UNMUTE:
            res = await self._device.mute(False)
        elif cmd_id == MediaPlayerCommands.ON:
            return StatusCodes.NOT_IMPLEMENTED
        elif cmd_id == MediaPlayerCommands.OFF:
            res = await self._device.power_off()
        elif cmd_id == MediaPlayerCommands.NEXT:
            res = await self._device.next()
        elif cmd_id == MediaPlayerCommands.PREVIOUS:
            res = await self._device.previous()
        elif cmd_id == MediaPlayerCommands.PLAY_PAUSE:
            res = await self._device.play_pause()
        elif cmd_id == MediaPlayerCommands.STOP:
            res = await self._device.stop()
        elif cmd_id == MediaPlayerCommands.HOME:
            res = await self._device.home()
        elif cmd_id == MediaPlayerCommands.SETTINGS:
            return StatusCodes.NOT_IMPLEMENTED # TODO ?
        elif cmd_id == MediaPlayerCommands.CONTEXT_MENU:
            res = await self._device.context_menu()
        elif cmd_id in KODI_BUTTONS_KEYMAP.keys():
            res = await self._device.command_button(KODI_BUTTONS_KEYMAP[cmd_id])
        elif cmd_id in KODI_ACTIONS_KEYMAP.keys():
            res = await self._device.command_action(KODI_ACTIONS_KEYMAP[cmd_id])
        elif cmd_id in self.options[Options.SIMPLE_COMMANDS]:
            res = await self._device.command_action(KODI_SIMPLE_COMMANDS[cmd_id])
        elif cmd_id == Commands.SEND_CMD:
            command = params.get("command", "")
            holdtime = params.get("hold", 0)
            res = await self._device.command_button({"button": command, "keymap": "R1", "holdtime": holdtime})
        elif cmd_id == Commands.SEND_CMD_SEQUENCE:
            delay = params.get("delay", 0)
            commands = params.get("sequence", "").split(",")
            res = StatusCodes.OK
            for command in commands:
                res = await self.command(Commands.SEND_CMD, {"command": command, "params": params})
                if delay > 0:
                    await asyncio.sleep(delay)
            return res
        else:
            return StatusCodes.NOT_IMPLEMENTED
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
            attributes = self._key_update_helper(Attributes.STATE, state, attributes)

        _LOG.debug("KodiRemote update attributes %s -> %s", update, attributes)
        return attributes

    def _key_update_helper(self, key: str, value: str | None, attributes):
        if value is None:
            return attributes

        if key in self.attributes:
            if self.attributes[key] != value:
                attributes[key] = value
        else:
            attributes[key] = value

        return attributes



