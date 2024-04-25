"""
Media-player entity functions.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

import kodi
from config import KodiConfigDevice, create_entity_id
from ucapi import EntityTypes, MediaPlayer, StatusCodes
from ucapi.media_player import Attributes, Commands, DeviceClasses, States, MediaType, Options
from const import KODI_SIMPLE_COMMANDS, KODI_ACTIONS_KEYMAP, KODI_BUTTONS_KEYMAP

_LOG = logging.getLogger(__name__)


class KodiMediaPlayer(MediaPlayer):
    """Representation of a Kodi Media Player entity."""

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        self._device: kodi.KodiDevice = device
        _LOG.debug("KodiMediaPlayer init")
        entity_id = create_entity_id(config_device.id, EntityTypes.MEDIA_PLAYER)
        features = device.supported_features
        attributes = {
            Attributes.STATE: kodi.KODI_STATE_MAPPING.get(device.state),
            Attributes.VOLUME: device.volume_level,
            Attributes.MUTED: device.is_volume_muted,
            Attributes.MEDIA_IMAGE_URL: device.media_image_url if device.media_image_url else "",
            Attributes.MEDIA_TITLE: device.media_title if device.media_title else "",
            Attributes.MEDIA_TYPE: device.media_type,
            Attributes.MEDIA_ALBUM: device.media_album,
            Attributes.MEDIA_ARTIST: device.media_artist,
            Attributes.MEDIA_POSITION: device.media_position,
            Attributes.MEDIA_DURATION: device.media_duration,
        }

        # # use sound mode support & name from configuration: receiver might not yet be connected
        # if device.support_sound_mode:
        #     features.append(Features.SELECT_SOUND_MODE)
        #     attributes[Attributes.SOUND_MODE] = ""
        #     attributes[Attributes.SOUND_MODE_LIST] = []
        options = {
            Options.SIMPLE_COMMANDS: list(KODI_SIMPLE_COMMANDS.keys())
        }
        super().__init__(
            entity_id,
            config_device.name,
            features,
            attributes,
            device_class=DeviceClasses.RECEIVER,
            options=options
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
        elif cmd_id == Commands.ON: #TODO the entity remains active otherwise
            res = StatusCodes.OK
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
            return StatusCodes.NOT_IMPLEMENTED # TODO ?
        elif cmd_id == Commands.CONTEXT_MENU:
            res = await self._device.context_menu()
        elif cmd_id == Commands.SEEK:
            media_position = params.get("media_position", 0)
            res = await self._device.seek(media_position)
        elif cmd_id in KODI_BUTTONS_KEYMAP.keys():
            res = await self._device.command_button(KODI_BUTTONS_KEYMAP[cmd_id])
        elif cmd_id in KODI_ACTIONS_KEYMAP.keys():
            res = await self._device.command_action(KODI_ACTIONS_KEYMAP[cmd_id])
        elif cmd_id in self.options[Options.SIMPLE_COMMANDS]:
            res = await self._device.command_action(KODI_SIMPLE_COMMANDS[cmd_id])
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
            state = update[Attributes.STATE]
            attributes = self._key_update_helper(Attributes.STATE, state, attributes)

        for attr in [
            Attributes.MEDIA_ARTIST,
            Attributes.MEDIA_ALBUM,
            Attributes.MEDIA_IMAGE_URL,
            Attributes.MEDIA_TITLE,
            Attributes.MEDIA_POSITION,
            Attributes.MEDIA_DURATION,
            Attributes.MEDIA_IMAGE_URL,
            Attributes.MUTED,
            Attributes.SOURCE,
            Attributes.VOLUME,
            Attributes.MEDIA_TYPE,
        ]:
            if attr in update:
                attributes = self._key_update_helper(attr, update[attr], attributes)

        if Attributes.SOURCE_LIST in update:
            if Attributes.SOURCE_LIST in self.attributes:
                if update[Attributes.SOURCE_LIST] != self.attributes[Attributes.SOURCE_LIST]:
                    attributes[Attributes.SOURCE_LIST] = update[Attributes.SOURCE_LIST]

        if Attributes.STATE in attributes:
            if attributes[Attributes.STATE] == States.OFF:
                attributes[Attributes.MEDIA_IMAGE_URL] = ""
                attributes[Attributes.MEDIA_TITLE] = ""
                attributes[Attributes.MEDIA_ALBUM] = ""
                attributes[Attributes.MEDIA_ARTIST] = ""
                attributes[Attributes.MEDIA_TYPE] = MediaType.VIDEO
                attributes[Attributes.SOURCE] = ""
        _LOG.debug("KodiMediaPlayer update attributes %s -> %s", update, attributes)
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



