"""
Media-player entity functions.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

import ucapi.media_player
from ucapi import EntityTypes, Sensor
from ucapi.media_player import States as MediaStates
from ucapi.sensor import Attributes, DeviceClasses, States

import kodi
from config import KodiConfigDevice, KodiEntity, create_entity_id
from const import KodiSensors

_LOG = logging.getLogger(__name__)

KODI_SENSOR_STATE_MAPPING = {
    MediaStates.OFF: States.UNAVAILABLE,
    MediaStates.ON: States.ON,
    MediaStates.STANDBY: States.ON,
    MediaStates.PLAYING: States.ON,
    MediaStates.PAUSED: States.ON,
    MediaStates.UNAVAILABLE: States.UNAVAILABLE,
    MediaStates.UNKNOWN: States.UNKNOWN,
}


class KodiSensor(KodiEntity, Sensor):
    """Representation of a Kodi Sensor entity."""

    def __init__(self, entity_id: str, name: str, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        # pylint: disable = R0801
        self._device: kodi.KodiDevice = device
        _LOG.debug("KodiSensor init")
        features = []
        attributes = dict[Any, Any]()
        self._config_device = config_device
        self._device: kodi.KodiDevice = device
        self._state: States = States.UNAVAILABLE
        super().__init__(entity_id, name, features, attributes, device_class=DeviceClasses.CUSTOM)

    @property
    def deviceid(self) -> str:
        """Return device identifier."""
        return self._device.id

    def update_attributes(self, update: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return the updated attributes of current sensor entity."""
        raise NotImplementedError()


class KodiAudioStream(KodiSensor):
    """Current audio stream sensor entity."""

    ENTITY_NAME = "audio_stream"

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        entity_id = f"{create_entity_id(config_device.id, EntityTypes.SENSOR)}.{KodiAudioStream.ENTITY_NAME}"
        # TODO : dict instead of name to report language names
        self._device = device
        self._config_device = config_device
        super().__init__(entity_id, "Audio stream", config_device, device)

    def update_attributes(self, update: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Return updated sensor value from full update if provided or sensor value if no udpate is provided."""
        attributes: dict[str, Any] = {}
        if update:
            if ucapi.media_player.Attributes.STATE in update:
                attributes[Attributes.STATE] = KODI_SENSOR_STATE_MAPPING.get(
                    update[ucapi.media_player.Attributes.STATE]
                )
            if KodiSensors.AUDIO_STREAM in update:
                attributes[Attributes.VALUE] = update[KodiSensors.AUDIO_STREAM]
            return attributes
        return {
            Attributes.VALUE: self._device.current_audio_track,
            Attributes.STATE: KODI_SENSOR_STATE_MAPPING.get(self._device.state),
        }


class KodiSubtitleStream(KodiSensor):
    """Current subtitle stream sensor entity."""

    ENTITY_NAME = "subtitle_stream"

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        entity_id = f"{create_entity_id(config_device.id, EntityTypes.SENSOR)}.{KodiSubtitleStream.ENTITY_NAME}"
        super().__init__(entity_id, "Subtitle stream", config_device, device)

    def update_attributes(self, update: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Return updated sensor value from full update if provided or sensor value if no udpate is provided."""
        attributes: dict[str, Any] = {}
        if update:
            if ucapi.media_player.Attributes.STATE in update:
                attributes[Attributes.STATE] = KODI_SENSOR_STATE_MAPPING.get(
                    update[ucapi.media_player.Attributes.STATE]
                )
            if KodiSensors.SUBTITLE_STREAM in update:
                attributes[Attributes.VALUE] = update[KodiSensors.SUBTITLE_STREAM]
            return attributes
        return {
            Attributes.VALUE: self._device.current_subtitle_track,
            Attributes.STATE: KODI_SENSOR_STATE_MAPPING.get(self._device.state),
        }


class KodiChapter(KodiSensor):
    """Current chapter sensor entity."""

    ENTITY_NAME = "chapter"

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        entity_id = f"{create_entity_id(config_device.id, EntityTypes.SENSOR)}.{KodiChapter.ENTITY_NAME}"
        super().__init__(entity_id, "Chapter", config_device, device)

    def update_attributes(self, update: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Return updated sensor value from full update if provided or sensor value if no udpate is provided."""
        attributes: dict[str, Any] = {}
        if update:
            if ucapi.media_player.Attributes.STATE in update:
                attributes[Attributes.STATE] = KODI_SENSOR_STATE_MAPPING.get(
                    update[ucapi.media_player.Attributes.STATE]
                )
            if KodiSensors.CHAPTER in update:
                attributes[Attributes.VALUE] = update[KodiSensors.CHAPTER]
            return attributes
        return {
            Attributes.VALUE: self._device.current_chapter,
            Attributes.STATE: KODI_SENSOR_STATE_MAPPING.get(self._device.state),
        }
