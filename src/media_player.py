"""
Media-player entity functions.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

import kodi
from config import KodiConfigDevice, create_entity_id
from const import (
    KODI_ACTIONS_KEYMAP,
    KODI_BUTTONS_KEYMAP,
    KODI_SIMPLE_COMMANDS,
    KODI_SIMPLE_COMMANDS_DIRECT, KODI_ALTERNATIVE_BUTTONS_KEYMAP, KODI_ADVANCED_SIMPLE_COMMANDS,
)
from ucapi import EntityTypes, MediaPlayer, StatusCodes
from ucapi.media_player import Attributes, Commands, DeviceClasses, Options

_LOG = logging.getLogger(__name__)


class KodiMediaPlayer(MediaPlayer):
    """Representation of a Kodi Media Player entity."""

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        # pylint: disable = R0801
        self._device: kodi.KodiDevice = device
        _LOG.debug("KodiMediaPlayer init")
        entity_id = create_entity_id(config_device.id, EntityTypes.MEDIA_PLAYER)
        features = device.supported_features
        attributes = device.attributes

        # # use sound mode support & name from configuration: receiver might not yet be connected
        # if device.support_sound_mode:
        #     features.append(Features.SELECT_SOUND_MODE)
        #     attributes[Attributes.SOUND_MODE] = ""
        #     attributes[Attributes.SOUND_MODE_LIST] = []
        simple_commands = [
            *list(KODI_SIMPLE_COMMANDS.keys()),
            *list(KODI_ADVANCED_SIMPLE_COMMANDS.keys())
        ]
        simple_commands.sort()
        options = {Options.SIMPLE_COMMANDS: simple_commands}
        super().__init__(
            entity_id, config_device.name, features, attributes, device_class=DeviceClasses.RECEIVER, options=options
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

        if cmd_id == Commands.VOLUME:
            res = await self._device.set_volume_level(params.get("volume"))
        elif cmd_id == Commands.VOLUME_UP:
            res = await self._device.volume_up()
        elif cmd_id == Commands.VOLUME_DOWN:
            res = await self._device.volume_down()
        elif cmd_id == Commands.MUTE_TOGGLE:
            res = await self._device.mute(not self.attributes[Attributes.MUTED])
        elif cmd_id == Commands.MUTE:
            res = await self._device.mute(True)
        elif cmd_id == Commands.UNMUTE:
            res = await self._device.mute(False)
        elif cmd_id == Commands.ON:
            res = await self._device.power_on()
        elif cmd_id == Commands.OFF:
            res = await self._device.power_off()
        elif cmd_id == Commands.NEXT:
            res = await self._device.next()
        elif cmd_id == Commands.PREVIOUS:
            res = await self._device.previous()
        elif cmd_id == Commands.PLAY_PAUSE:
            res = await self._device.play_pause()
        elif cmd_id == Commands.STOP:
            res = await self._device.stop()
        elif cmd_id == Commands.HOME:
            res = await self._device.home()
        elif cmd_id == Commands.SETTINGS:
            return StatusCodes.NOT_IMPLEMENTED  # TODO ?
        elif cmd_id == Commands.CONTEXT_MENU:
            res = await self._device.context_menu()
        elif cmd_id == Commands.SEEK:
            media_position = params.get("media_position", 0)
            res = await self._device.seek(media_position)
        elif not self._device.device_config.disable_keyboard_map and cmd_id in KODI_BUTTONS_KEYMAP:
            res = await self._device.command_button(KODI_BUTTONS_KEYMAP[cmd_id])
        elif self._device.device_config.disable_keyboard_map and cmd_id in KODI_ALTERNATIVE_BUTTONS_KEYMAP:
            command = KODI_ALTERNATIVE_BUTTONS_KEYMAP[cmd_id]
            res = await self._device.call_command(command["method"], **command["params"])
        elif cmd_id in KODI_ACTIONS_KEYMAP:
            res = await self._device.command_action(KODI_ACTIONS_KEYMAP[cmd_id])
        elif cmd_id in self.options[Options.SIMPLE_COMMANDS]:
            if cmd_id in KODI_ADVANCED_SIMPLE_COMMANDS:
                command = KODI_ADVANCED_SIMPLE_COMMANDS[cmd_id]
                res = await self._device.call_command(command["method"], **command["params"])
            else:
                command = KODI_SIMPLE_COMMANDS[cmd_id]
                if command in KODI_SIMPLE_COMMANDS_DIRECT:
                    res = await self._device.call_command(command)
                else:
                    res = await self._device.command_action(command)
        else:
            return StatusCodes.NOT_IMPLEMENTED
        return res
