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
    MediaStates.OFF: States.ON,
    MediaStates.ON: States.ON,
    MediaStates.STANDBY: States.ON,
    MediaStates.PLAYING: States.ON,
    MediaStates.PAUSED: States.ON,
    MediaStates.UNAVAILABLE: States.UNAVAILABLE,
    MediaStates.UNKNOWN: States.UNKNOWN,
}


class KodiSensor(KodiEntity, Sensor):
    """Representation of a Kodi Sensor entity."""

    ENTITY_NAME = "sensor"
    SENSOR_NAME: KodiSensors

    def __init__(
        self, entity_id: str, name: str | dict[str, str], config_device: KodiConfigDevice, device: kodi.KodiDevice
    ):
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

    @property
    def state(self) -> States:
        """Return sensor state."""
        raise self._state

    @property
    def sensor_value(self) -> str:
        """Return sensor value."""
        raise NotImplementedError()

    def update_attributes(self, update: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Return updated sensor value from full update if provided or sensor value if no udpate is provided."""
        attributes: dict[str, Any] = {}
        if update:
            if ucapi.media_player.Attributes.STATE in update:
                new_state = KODI_SENSOR_STATE_MAPPING.get(update[ucapi.media_player.Attributes.STATE])
                if new_state != self._state:
                    self._state = new_state
                    attributes[Attributes.STATE] = self._state
            if self.SENSOR_NAME in update:
                attributes[Attributes.VALUE] = update[self.SENSOR_NAME]
            return attributes
        return {
            Attributes.VALUE: self.sensor_value,
            Attributes.STATE: KODI_SENSOR_STATE_MAPPING.get(self._device.state),
        }


class KodiAudioStream(KodiSensor):
    """Current audio stream sensor entity."""

    ENTITY_NAME = "audio_stream"
    SENSOR_NAME = KodiSensors.SENSOR_AUDIO_STREAM

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        entity_id = f"{create_entity_id(config_device.id, EntityTypes.SENSOR)}.{self.ENTITY_NAME}"
        # TODO : dict instead of name to report language names
        self._device = device
        self._config_device = config_device
        super().__init__(entity_id, {"en": "Audio stream", "fr": "Piste audio"}, config_device, device)

    @property
    def sensor_value(self) -> str:
        return self._device.current_audio_track if self._device.current_audio_track else ""


class KodiSubtitleStream(KodiSensor):
    """Current subtitle stream sensor entity."""

    ENTITY_NAME = "subtitle_stream"
    SENSOR_NAME = KodiSensors.SENSOR_SUBTITLE_STREAM

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        entity_id = f"{create_entity_id(config_device.id, EntityTypes.SENSOR)}.{self.ENTITY_NAME}"
        super().__init__(entity_id, {"en": "Subtitle stream", "fr": "Sous-titres"}, config_device, device)

    @property
    def sensor_value(self) -> str:
        return self._device.current_subtitle_track if self._device.current_subtitle_track else ""


class KodiChapter(KodiSensor):
    """Current chapter sensor entity."""

    ENTITY_NAME = "chapter"
    SENSOR_NAME = KodiSensors.SENSOR_CHAPTER

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        entity_id = f"{create_entity_id(config_device.id, EntityTypes.SENSOR)}.{self.ENTITY_NAME}"
        super().__init__(entity_id, {"en": "Chapter", "fr": "Chapitre"}, config_device, device)

    @property
    def sensor_value(self) -> str:
        return self._device.current_chapter if self._device.current_chapter else ""


class KodiVideoInfo(KodiSensor):
    """Current chapter sensor entity."""

    ENTITY_NAME = "video_info"
    SENSOR_NAME = KodiSensors.SENSOR_VIDEO_INFO

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        entity_id = f"{create_entity_id(config_device.id, EntityTypes.SENSOR)}.{self.ENTITY_NAME}"
        super().__init__(entity_id, {"en": "Video info", "fr": "Info vidéo"}, config_device, device)

    @property
    def sensor_value(self) -> str:
        return self._device.video_info
