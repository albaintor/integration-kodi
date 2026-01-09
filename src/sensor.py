"""
Media-player entity functions.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

from ucapi import EntityTypes, Sensor
from ucapi.sensor import Attributes, DeviceClasses

import kodi
from config import KodiConfigDevice, KodiEntity, create_entity_id
from const import KodiSensors

_LOG = logging.getLogger(__name__)


class KodiSensor(KodiEntity, Sensor):
    """Representation of a Kodi Sensor entity."""

    def __init__(self, entity_id: str, name: str, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        # pylint: disable = R0801
        self._device: kodi.KodiDevice = device
        _LOG.debug("KodiMediaPlayer init")
        features = []
        attributes = dict[Any, Any]()
        self._config_device = config_device
        self._device: kodi.KodiDevice = device
        super().__init__(entity_id, name, features, attributes, device_class=DeviceClasses.CUSTOM)

    @property
    def deviceid(self) -> str:
        return self._device.id

    def update_attributes(self, update: dict[str, Any] | None = None) -> dict[str, Any]:
        """Returns the updated attributes of current sensor entity."""
        raise NotImplementedError()


class KodiAudioStream(KodiSensor):
    """Current audio stream sensor entity."""

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        entity_id = create_entity_id(config_device.id, EntityTypes.SENSOR) + ".audio_stream"
        # TODO : dict instead of name to report language names
        super().__init__(entity_id, "Audio stream", config_device, device)

    def update_attributes(self, update: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Return updated sensor value from full update if provided or sensor value if no udpate is provided."""
        if update:
            if KodiSensors.AUDIO_STREAM in update:
                return {Attributes.VALUE: update[KodiSensors.AUDIO_STREAM]}
            return None
        return {Attributes.VALUE: self._device.current_audio_track}


class KodiSubtitleStream(KodiSensor):
    """Current subtitle stream sensor entity."""

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        entity_id = create_entity_id(config_device.id, EntityTypes.SENSOR) + ".subtitle_stream"
        super().__init__(entity_id, "Subtitle stream", config_device, device)

    def update_attributes(self, update: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Return updated sensor value from full update if provided or sensor value if no udpate is provided."""
        if update:
            if KodiSensors.SUBTITLE_STREAM in update:
                return {Attributes.VALUE: update[KodiSensors.AUDIO_STREAM]}
            return None
        return {Attributes.VALUE: self._device.current_subtitle_track}


class KodiChapter(KodiSensor):
    """Current chapter sensor entity."""

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        entity_id = create_entity_id(config_device.id, EntityTypes.SENSOR) + ".chapter"
        super().__init__(entity_id, "Chapter", config_device, device)

    def update_attributes(self, update: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Return updated sensor value from full update if provided or sensor value if no udpate is provided."""
        if update:
            if KodiSensors.CHAPTER in update:
                return {Attributes.VALUE: update[KodiSensors.CHAPTER]}
            return None
        return {Attributes.VALUE: self._device.current_chapter}
