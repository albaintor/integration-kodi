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
from ucapi.sensor import Attributes, DeviceClasses, Options, States

import kodi
from config import KodiConfigDevice, KodiEntity, create_entity_id
from const import KodiSensors, KODI_DEFAULT_NAME

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


# pylint: disable=R0917
class KodiSensor(KodiEntity, Sensor):
    """Representation of a Kodi Sensor entity."""

    ENTITY_NAME = "sensor"
    SENSOR_NAME: KodiSensors

    def __init__(
        self,
        entity_id: str,
        name: str | dict[str, str],
        config_device: KodiConfigDevice,
        device: kodi.KodiDevice,
        options: dict[Options, Any] | None = None,
        device_class: DeviceClasses = DeviceClasses.CUSTOM,
    ):
        """Initialize the class."""
        # pylint: disable = R0801
        self._device: kodi.KodiDevice = device
        features = []
        attributes = dict[Any, Any]()
        self._config_device = config_device
        self._device: kodi.KodiDevice = device
        self._state: States = States.UNAVAILABLE
        super().__init__(entity_id, name, features, attributes, device_class=device_class, options=options)

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
        if self._config_device.sensor_include_device_name:
            name = config_device.name + " " if config_device.name != KODI_DEFAULT_NAME else ""
        else:
            name = ""
        super().__init__(entity_id, {"en": f"{name}Audio stream", "fr": f"{name}Piste audio"}, config_device, device)

    @property
    def sensor_value(self) -> str:
        """Return sensor value."""
        return self._device.sensor_audio_stream


class KodiSubtitleStream(KodiSensor):
    """Current subtitle stream sensor entity."""

    ENTITY_NAME = "subtitle_stream"
    SENSOR_NAME = KodiSensors.SENSOR_SUBTITLE_STREAM

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        entity_id = f"{create_entity_id(config_device.id, EntityTypes.SENSOR)}.{self.ENTITY_NAME}"
        if config_device.sensor_include_device_name:
            name = config_device.name + " " if config_device.name != KODI_DEFAULT_NAME else ""
        else:
            name = ""
        super().__init__(entity_id, {"en": f"{name}Subtitle stream", "fr": f"{name}Sous-titres"}, config_device, device)

    @property
    def sensor_value(self) -> str:
        """Return sensor value."""
        return self._device.sensor_subtitle_stream


class KodiChapter(KodiSensor):
    """Current chapter sensor entity."""

    ENTITY_NAME = "chapter"
    SENSOR_NAME = KodiSensors.SENSOR_CHAPTER

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        entity_id = f"{create_entity_id(config_device.id, EntityTypes.SENSOR)}.{self.ENTITY_NAME}"
        if config_device.sensor_include_device_name:
            name = config_device.name + " " if config_device.name != KODI_DEFAULT_NAME else ""
        else:
            name = ""
        super().__init__(entity_id, {"en": f"{name}Chapter", "fr": f"{name}Chapitre"}, config_device, device)

    @property
    def sensor_value(self) -> str:
        """Return sensor value."""
        return self._device.current_chapter if self._device.current_chapter else ""


class KodiVideoInfo(KodiSensor):
    """Current chapter sensor entity."""

    ENTITY_NAME = "video_info"
    SENSOR_NAME = KodiSensors.SENSOR_VIDEO_INFO

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        entity_id = f"{create_entity_id(config_device.id, EntityTypes.SENSOR)}.{self.ENTITY_NAME}"
        if config_device.sensor_include_device_name:
            name = config_device.name + " " if config_device.name != KODI_DEFAULT_NAME else ""
        else:
            name = ""
        super().__init__(entity_id, {"en": f"{name}Video info", "fr": f"{name}Info vidéo"}, config_device, device)

    @property
    def sensor_value(self) -> str:
        """Return sensor value."""
        return self._device.video_info


class KodiSensorVolume(KodiSensor):
    """Current input source sensor entity."""

    ENTITY_NAME = "sensor_volume"
    SENSOR_NAME = KodiSensors.SENSOR_VOLUME

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        entity_id = f"{create_entity_id(config_device.id, EntityTypes.SENSOR)}.{self.ENTITY_NAME}"
        self._device = device
        self._config_device = config_device
        options = {
            Options.CUSTOM_UNIT: "%",
            Options.MIN_VALUE: 0,
            Options.MAX_VALUE: 100,
        }
        if config_device.sensor_include_device_name:
            name = config_device.name + " " if config_device.name != KODI_DEFAULT_NAME else ""
        else:
            name = ""
        super().__init__(entity_id, {"en": f"{name}Volume", "fr": f"{name}Volume"}, config_device, device, options)

    @property
    def sensor_value(self) -> str | float:
        """Return sensor value."""
        return self._device.volume_level if self._device.volume_level else 0


class KodiSensorMuted(KodiSensor):
    """Current mute state sensor entity."""

    ENTITY_NAME = "sensor_muted"
    SENSOR_NAME = KodiSensors.SENSOR_VOLUME_MUTED

    def __init__(self, config_device: KodiConfigDevice, device: kodi.KodiDevice):
        """Initialize the class."""
        entity_id = f"{create_entity_id(config_device.id, EntityTypes.SENSOR)}.{self.ENTITY_NAME}"
        self._device = device
        self._config_device = config_device
        if config_device.sensor_include_device_name:
            name = config_device.name + " " if config_device.name != KODI_DEFAULT_NAME else ""
        else:
            name = ""
        super().__init__(
            entity_id,
            {"en": f"{name}Muted", "fr": f"{name}Son coupé"},
            config_device,
            device,
            None,
            DeviceClasses.BINARY,
        )

    @property
    def sensor_value(self) -> str | float:
        """Return sensor value."""
        return "on" if self._device.is_volume_muted else "off"
