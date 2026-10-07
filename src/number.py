"""
Number entity functions.

This module contains a small compatibility implementation of the Core API number
entity until it is available in the ucapi Python library.

:copyright: (c) 2026 by Albaintor
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
import math
from enum import StrEnum
from typing import Any

from ucapi import Entity, StatusCodes
from ucapi.api_definitions import CommandHandler
from ucapi.media_player import Attributes as MediaAttributes
from ucapi.media_player import States as MediaStates

import kodi_device
from config import KodiConfigDevice, KodiEntity, create_entity_id

_LOG = logging.getLogger(__name__)

Numeric = int | float


class EntityTypes(StrEnum):
    """Number entity types missing from the current ucapi release."""

    NUMBER = "number"


class States(StrEnum):
    """Number entity states."""

    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"
    ON = "ON"


class Features(StrEnum):
    """Number entity features."""

    VALUE = "value"


class Attributes(StrEnum):
    """Number entity attributes."""

    STATE = "state"
    VALUE = "value"


class Commands(StrEnum):
    """Number entity commands."""

    SET_VALUE = "set_value"
    INCREMENT = "increment"
    DECREMENT = "decrement"


class DeviceClasses(StrEnum):
    """Number entity device classes.

    The Core API does not currently define number device classes.
    """


class Options(StrEnum):
    """Number entity options."""

    MIN = "min"
    MAX = "max"
    STEP = "step"
    DECIMALS = "decimals"
    UNIT = "unit"
    READABLE = "readable"


class Number(Entity):
    """Compatibility implementation of the Core API number entity."""

    # pylint: disable=R0917
    def __init__(
        self,
        identifier: str,
        name: str | dict[str, str],
        features: list[Features],
        attributes: dict[str, Any],
        *,
        options: dict[Options, Any] | None = None,
        icon: str | None = None,
        description: str | dict[str, str] | None = None,
        area: str | None = None,
        cmd_handler: CommandHandler = None,
    ):
        """Create a number entity instance."""
        number_features = list(features)
        if Features.VALUE not in number_features:
            number_features.append(Features.VALUE)
        super().__init__(
            identifier,
            name,
            EntityTypes.NUMBER,
            number_features,
            attributes,
            options=options,
            icon=icon,
            description=description,
            area=area,
            cmd_handler=cmd_handler,
        )


KODI_NUMBER_STATE_MAPPING = {
    MediaStates.OFF: States.ON,
    MediaStates.ON: States.ON,
    MediaStates.STANDBY: States.ON,
    MediaStates.PLAYING: States.ON,
    MediaStates.PAUSED: States.ON,
    MediaStates.UNAVAILABLE: States.UNAVAILABLE,
    MediaStates.UNKNOWN: States.UNKNOWN,
}


class KodiNumber(KodiEntity, Number):
    """Base class for a writable Kodi number entity."""

    UPDATE_ATTRIBUTES: set[MediaAttributes] = set()

    def __init__(
        self,
        entity_id: str,
        name: str | dict[str, str],
        config_device: KodiConfigDevice,
        device: kodi_device.KodiDevice,
        options: dict[Options, Any],
    ):
        """Initialize a Kodi number entity."""
        self._config_device = config_device
        self._device = device
        self._state = KODI_NUMBER_STATE_MAPPING.get(device.state, States.UNKNOWN)
        self._minimum: Numeric = options.get(Options.MIN, 0)
        self._maximum: Numeric = options.get(Options.MAX, 100)
        self._step: Numeric = options.get(Options.STEP, 1)
        self._decimals: int = options.get(Options.DECIMALS, 0)
        super().__init__(
            entity_id,
            name,
            [Features.VALUE],
            self.all_attributes,
            options=options,
        )

    @property
    def deviceid(self) -> str:
        """Return device identifier."""
        return self._device.id

    @property
    def number_value(self) -> Numeric:
        """Return the current number value."""
        raise NotImplementedError()

    @property
    def all_attributes(self) -> dict[str, Any]:
        """Return all number attributes."""
        return {
            Attributes.STATE: self._state,
            Attributes.VALUE: self.number_value,
        }

    def update_attributes(self, update: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return attributes affected by a Kodi device update."""
        if update is None:
            self._state = KODI_NUMBER_STATE_MAPPING.get(self._device.state, States.UNKNOWN)
            return self.all_attributes

        attributes: dict[str, Any] = {}
        if MediaAttributes.STATE in update:
            state = KODI_NUMBER_STATE_MAPPING.get(update[MediaAttributes.STATE], States.UNKNOWN)
            if state != self._state:
                self._state = state
                attributes[Attributes.STATE] = state

        if self.UPDATE_ATTRIBUTES.intersection(update):
            attributes[Attributes.VALUE] = self.number_value
        return attributes

    def _validated_value(self, value: Any, *, clamp: bool) -> Numeric | None:
        """Validate, optionally clamp, and round a command value."""
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None
        if clamp:
            value = min(max(value, self._minimum), self._maximum)
        elif value < self._minimum or value > self._maximum:
            return None
        if self._decimals == 0:
            return round(value)
        return round(value, self._decimals)

    async def _set_value(self, value: Numeric) -> StatusCodes:
        """Set the device value."""
        raise NotImplementedError()

    async def command(self, cmd_id: str, params: dict[str, Any] | None = None, *, websocket: Any) -> StatusCodes:
        """Process a number command."""
        _LOG.info("Got %s command request: %s %s", self.id, cmd_id, params)
        params = params or {}

        if cmd_id == Commands.SET_VALUE:
            value = self._validated_value(params.get("value"), clamp=False)
        elif cmd_id in (Commands.INCREMENT, Commands.DECREMENT):
            step = params.get("step", self._step)
            if (
                isinstance(step, bool)
                or not isinstance(step, (int, float))
                or not math.isfinite(step)
                or step <= 0
            ):
                return StatusCodes.BAD_REQUEST
            value = self.number_value + (step if cmd_id == Commands.INCREMENT else -step)
            value = self._validated_value(value, clamp=True)
        else:
            return StatusCodes.BAD_REQUEST

        if value is None:
            return StatusCodes.BAD_REQUEST
        return await self._set_value(value)


# class KodiNumberSeek(KodiNumber):
#     """Kodi playback position as a percentage number entity."""
#
#     ENTITY_NAME = "seek"
#     UPDATE_ATTRIBUTES = {
#         MediaAttributes.STATE,
#         MediaAttributes.MEDIA_POSITION,
#         MediaAttributes.MEDIA_DURATION,
#     }
#
#     def __init__(self, config_device: KodiConfigDevice, device: kodi_device.KodiDevice):
#         """Initialize the seek number entity."""
#         entity_id = f"{create_entity_id(config_device.id, EntityTypes.NUMBER)}.{self.ENTITY_NAME}"
#         super().__init__(
#             entity_id,
#             {
#                 "en": f"{config_device.get_device_part()}Seek",
#                 "fr": f"{config_device.get_device_part()}Position de lecture",
#             },
#             config_device,
#             device,
#             {
#                 Options.MIN: 0,
#                 Options.MAX: 100,
#                 Options.STEP: 1,
#                 Options.DECIMALS: 0,
#                 Options.UNIT: "%",
#                 Options.READABLE: True,
#             },
#         )
#
#     @property
#     def number_value(self) -> Numeric:
#         """Return the current playback position as a percentage."""
#         duration = self._device.media_duration or 0
#         position = self._device.current_media_position or 0
#         if duration <= 0:
#             return 0
#         return round(min(max(position / duration * 100, 0), 100))
#
#     async def _set_value(self, value: Numeric) -> StatusCodes:
#         """Seek to a percentage of the current media duration."""
#         duration = self._device.media_duration or 0
#         media_position = round(duration * value / 100)
#         return await self._device.seek(media_position)
#
#
# class KodiNumberVolume(KodiNumber):
#     """Kodi volume number entity."""
#
#     ENTITY_NAME = "volume"
#     UPDATE_ATTRIBUTES = {MediaAttributes.VOLUME}
#
#     def __init__(self, config_device: KodiConfigDevice, device: kodi_device.KodiDevice):
#         """Initialize the volume number entity."""
#         entity_id = f"{create_entity_id(config_device.id, EntityTypes.NUMBER)}.{self.ENTITY_NAME}"
#         super().__init__(
#             entity_id,
#             {
#                 "en": f"{config_device.get_device_part()}Volume",
#                 "fr": f"{config_device.get_device_part()}Volume",
#             },
#             config_device,
#             device,
#             {
#                 Options.MIN: 0,
#                 Options.MAX: 100,
#                 Options.STEP: 1,
#                 Options.DECIMALS: 0,
#                 Options.UNIT: "%",
#                 Options.READABLE: True,
#             },
#         )
#
#     @property
#     def number_value(self) -> Numeric:
#         """Return the current Kodi volume."""
#         return self._device.volume_level or 0
#
#     async def _set_value(self, value: Numeric) -> StatusCodes:
#         """Set Kodi volume."""
#         return await self._device.set_volume_level(value)


class KodiNumberZoom(KodiNumber):
    """Kodi video zoom factor number entity."""

    ENTITY_NAME = "zoom"
    UPDATE_ATTRIBUTES = {"zoom"}

    def __init__(self, config_device: KodiConfigDevice, device: kodi_device.KodiDevice):
        """Initialize the video zoom entity."""
        entity_id = f"{create_entity_id(config_device.id, EntityTypes.NUMBER)}.{self.ENTITY_NAME}"
        super().__init__(
            entity_id,
            {
                "en": f"{config_device.get_device_part()}Video zoom",
                "fr": f"{config_device.get_device_part()}Zoom vidéo",
            },
            config_device,
            device,
            {
                Options.MIN: 0.5,
                Options.MAX: 2.0,
                Options.STEP: 0.01,
                Options.DECIMALS: 2,
                Options.READABLE: True,
            },
        )

    @property
    def number_value(self) -> Numeric:
        """Return the current video zoom factor."""
        return self._device.zoom_level

    async def _set_value(self, value: Numeric) -> StatusCodes:
        """Set the video zoom factor."""
        return await self._device.set_zoom_level(float(value))


class KodiNumberAudioDelay(KodiNumber):
    """Kodi audio delay number entity."""

    ENTITY_NAME = "audio_delay"
    UPDATE_ATTRIBUTES = {"audio_delay"}

    def __init__(self, config_device: KodiConfigDevice, device: kodi_device.KodiDevice):
        """Initialize the audio delay entity."""
        entity_id = f"{create_entity_id(config_device.id, EntityTypes.NUMBER)}.{self.ENTITY_NAME}"
        super().__init__(
            entity_id,
            {
                "en": f"{config_device.get_device_part()}Audio delay",
                "fr": f"{config_device.get_device_part()}Délai audio",
            },
            config_device,
            device,
            {
                Options.MIN: -10.0,
                Options.MAX: 10.0,
                Options.STEP: 0.025,
                Options.DECIMALS: 3,
                Options.UNIT: "s",
                Options.READABLE: True,
            },
        )

    @property
    def number_value(self) -> Numeric:
        """Return the current audio delay in seconds."""
        return self._device.audio_delay_level

    async def _set_value(self, value: Numeric) -> StatusCodes:
        """Set the absolute audio delay in seconds."""
        return await self._device.set_audio_delay(float(value))
