#!/usr/bin/env python3
"""
This module implements a Remote Two integration driver for Kodi receivers.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import asyncio
import logging
import os
from typing import Any

import kodi
import config
import media_player
import setup_flow
import ucapi
from config import device_from_entity_id
from ucapi.media_player import Attributes as MediaAttr

_LOG = logging.getLogger("driver")  # avoid having __main__ in log messages
_LOOP = asyncio.get_event_loop()

# Global variables
api = ucapi.IntegrationAPI(_LOOP)
# Map of id -> LG instance
_configured_kodis: dict[str, kodi.KodiDevice] = {}
_R2_IN_STANDBY = False


@api.listens_to(ucapi.Events.CONNECT)
async def on_r2_connect_cmd() -> None:
    """Connect all configured TVs when the Remote Two sends the connect command."""
    # TODO check if we were in standby and ignore the call? We'll also get an EXIT_STANDBY
    _LOG.debug("R2 connect command: connecting device(s)")
    for device in _configured_kodis.values():
        # start background task
        # TODO ? what is the connect event for (against exit from standby)
        # await _LOOP.create_task(device.power_on())
        try:
            await _LOOP.create_task(device.connect())
        except Exception as ex:
            _LOG.debug("Could not connect to device %s", ex)
    await api.set_device_state(ucapi.DeviceStates.CONNECTED)


@api.listens_to(ucapi.Events.DISCONNECT)
async def on_r2_disconnect_cmd():
    """Disconnect all configured TVs when the Remote Two sends the disconnect command."""
    if len(api._clients) == 0:
        _LOG.debug("Disconnect requested")
        for device in _configured_kodis.values():
            # start background task
            await _LOOP.create_task(device.disconnect())
    else:
        _LOG.debug("Disconnect requested but 1 client is connected %s", api._clients)


@api.listens_to(ucapi.Events.ENTER_STANDBY)
async def on_r2_enter_standby() -> None:
    """
    Enter standby notification from Remote Two.

    Disconnect every Kodi instances.
    """
    global _R2_IN_STANDBY

    _R2_IN_STANDBY = True
    if len(api._clients) == 0:
        _LOG.debug("Enter standby event: disconnecting device(s)")
        for configured in _configured_kodis.values():
            await configured.disconnect()
    else:
        _LOG.debug("Enter standby event: keeping alive while as it remains clients %s", api._clients)


@api.listens_to(ucapi.Events.EXIT_STANDBY)
async def on_r2_exit_standby() -> None:
    """
    Exit standby notification from Remote Two.

    Connect all Kodi instances.
    """
    global _R2_IN_STANDBY

    _R2_IN_STANDBY = False
    _LOG.debug("Exit standby event: connecting device(s)")

    for configured in _configured_kodis.values():
        # start background task
        try:
            await _LOOP.create_task(configured.connect())
        except Exception as ex:
            _LOG.error("Error while reconnecting to Kodi %s", ex)
        # _LOOP.create_task(configured.connect())


@api.listens_to(ucapi.Events.SUBSCRIBE_ENTITIES)
async def on_subscribe_entities(entity_ids: list[str]) -> None:
    """
    Subscribe to given entities.

    :param entity_ids: entity identifiers.
    """
    global _R2_IN_STANDBY

    _R2_IN_STANDBY = False
    _LOG.debug("Subscribe entities event: %s", entity_ids)
    for entity_id in entity_ids:
        device_id = device_from_entity_id(entity_id)
        if device_id in _configured_kodis:
            device = _configured_kodis[device_id]
            state = kodi.KODI_STATE_MAPPING.get(device.state)
            api.configured_entities.update_attributes(entity_id, {ucapi.media_player.Attributes.STATE: state})
            continue

        device = config.devices.get(device_id)
        if device:
            _configure_new_device(device, connect=True)
            _LOOP.create_task(device.connect())
        else:
            _LOG.error("Failed to subscribe entity %s: no Kodi configuration found", entity_id)


@api.listens_to(ucapi.Events.UNSUBSCRIBE_ENTITIES)
async def on_unsubscribe_entities(entity_ids: list[str]) -> None:
    """On unsubscribe, we disconnect the objects and remove listeners for events."""
    _LOG.debug("Unsubscribe entities event: %s", entity_ids)
    for entity_id in entity_ids:
        device_id = device_from_entity_id(entity_id)
        if device_id is None:
            continue
        if device_id in _configured_kodis:
            # TODO #21 this doesn't work once we have more than one entity per device!
            # --- START HACK ---
            # Since a device instance only provides exactly one media-player, it's save to disconnect if the entity is
            # unsubscribed. This should be changed to a more generic logic, also as template for other integrations!
            # Otherwise this sets a bad copy-paste example and leads to more issues in the future.
            # --> correct logic: check configured_entities, if empty: disconnect
            await _configured_kodis[entity_id].disconnect()
            _configured_kodis[entity_id].events.remove_all_listeners()


async def on_device_connected(device_id: str):
    """Handle device connection."""
    _LOG.debug("Kodi connected: %s", device_id)

    if device_id not in _configured_kodis:
        _LOG.warning("Kodi %s is not configured", device_id)
        return

    # TODO #20 when multiple devices are supported, the device state logic isn't that simple anymore!
    await api.set_device_state(ucapi.DeviceStates.CONNECTED)

    for entity_id in _entities_from_device_id(device_id):
        configured_entity = api.configured_entities.get(entity_id)
        if configured_entity is None:
            continue

        if configured_entity.entity_type == ucapi.EntityTypes.MEDIA_PLAYER:
            if (
                    configured_entity.attributes[ucapi.media_player.Attributes.STATE]
                    == ucapi.media_player.States.UNAVAILABLE
            ):
                # TODO why STANDBY?
                api.configured_entities.update_attributes(
                    entity_id, {ucapi.media_player.Attributes.STATE: ucapi.media_player.States.STANDBY}
                )


async def on_device_disconnected(device_id: str):
    """Handle device disconnection."""
    _LOG.debug("Kodi disconnected: %s", device_id)

    for entity_id in _entities_from_device_id(device_id):
        configured_entity = api.configured_entities.get(entity_id)
        if configured_entity is None:
            continue

        if configured_entity.entity_type == ucapi.EntityTypes.MEDIA_PLAYER:
            api.configured_entities.update_attributes(
                entity_id, {ucapi.media_player.Attributes.STATE: ucapi.media_player.States.UNAVAILABLE}
            )

    # TODO #20 when multiple devices are supported, the device state logic isn't that simple anymore!
    await api.set_device_state(ucapi.DeviceStates.DISCONNECTED)


async def on_device_connection_error(device_id: str, message):
    """Set entities of Kodi to state UNAVAILABLE if device connection error occurred."""
    _LOG.error(message)

    for entity_id in _entities_from_device_id(device_id):
        configured_entity = api.configured_entities.get(entity_id)
        if configured_entity is None:
            continue

        if configured_entity.entity_type == ucapi.EntityTypes.MEDIA_PLAYER:
            api.configured_entities.update_attributes(
                entity_id, {ucapi.media_player.Attributes.STATE: ucapi.media_player.States.UNAVAILABLE}
            )

    # TODO #20 when multiple devices are supported, the device state logic isn't that simple anymore!
    await api.set_device_state(ucapi.DeviceStates.ERROR)


async def handle_device_address_change(device_id: str, address: str) -> None:
    """Update device configuration with changed IP address."""
    # TODO discover
    device = config.devices.get(device_id)
    if device and device.address != address:
        _LOG.info("Updating IP address of configured Kodi %s: %s -> %s", device_id, device.address, address)
        device.address = address
        config.devices.update(device)


async def on_device_update(device_id: str, update: dict[str, Any] | None) -> None:
    """
    Update attributes of configured media-player entity if device properties changed.

    :param device_id: device identifier
    :param update: dictionary containing the updated properties or None if
    """
    if update is None:
        if device_id not in _configured_kodis:
            return
        device = _configured_kodis[device_id]
        update = {
            MediaAttr.STATE: kodi.KODI_STATE_MAPPING.get(device.state),
            MediaAttr.VOLUME: device.volume_level,
            MediaAttr.MUTED: device.is_volume_muted,
            MediaAttr.MEDIA_IMAGE_URL: device.media_image_url if device.media_image_url else "",
            MediaAttr.MEDIA_TITLE: device.media_title if device.media_title else "",
            MediaAttr.MEDIA_TYPE: device.media_type,
            MediaAttr.MEDIA_ALBUM: device.media_album,
            MediaAttr.MEDIA_ARTIST: device.media_artist,
            MediaAttr.MEDIA_POSITION: device.media_position,
            MediaAttr.MEDIA_DURATION: device.media_duration,
        }
    else:
        _LOG.info("[%s] Kodi update: %s", device_id, update)

    attributes = None

    # TODO awkward logic: this needs better support from the integration library
    _LOG.info("Update device %s for configured devices %s", device_id, api.configured_entities)
    for entity_id in _entities_from_device_id(device_id):

        configured_entity = api.configured_entities.get(entity_id)
        if configured_entity is None:
            return

        if isinstance(configured_entity, media_player.KodiMediaPlayer):
            attributes = configured_entity.filter_changed_attributes(update)

        if attributes:
            api.configured_entities.update_attributes(entity_id, attributes)


def _entities_from_device_id(device_id: str) -> list[str]:
    """
    Return all associated entity identifiers of the given device.

    :param device_id: the device identifier
    :return: list of entity identifiers
    """
    # dead simple for now: one media_player entity per device!
    # TODO #21 support multiple zones: one media-player per zone
    return [f"media_player.{device_id}"]


def _configure_new_device(device_config: config.KodiConfigDevice, connect: bool = True) -> None:
    """
    Create and configure a new device.

    Supported entities of the device are created and registered in the integration library as available entities.

    :param device: the receiver configuration.
    :param connect: True: start connection to receiver.
    """
    # the device should not yet be configured, but better be safe
    if device_config.id in _configured_kodis:
        device = _configured_kodis[device_config.id]
        device.disconnect()
    else:
        device = kodi.KodiDevice(device_config, loop=_LOOP)

        on_device_connected(device.id)
        # asyncio.rundevice.events.on(lg.Events.CONNECTED, on_device_connected)
        # device.events.on(lg.Events.DISCONNECTED, on_device_disconnected)
        device.events.on(kodi.Events.ERROR, on_device_connection_error)
        device.events.on(kodi.Events.UPDATE, on_device_update)
        # TODO event change address
        # receiver.events.on(lg.Events.IP_ADDRESS_CHANGED, handle_lg_address_change)
        # receiver.connect()
        _configured_kodis[device.id] = device

    _register_available_entities(device_config, device)

    if connect:
        # start background connection task
        try:
            _LOOP.create_task(device.connect())
        except Exception as ex:
            _LOG.debug("Could not connect to device, probably because it is starting with magic packet %s", ex)


def _register_available_entities(device_config: config.KodiConfigDevice, device: kodi.KodiDevice) -> None:
    """
    Create entities for given receiver device and register them as available entities.

    :param device_config: Receiver
    """
    # plain and simple for now: only one media_player per device
    # entity = media_player.create_entity(device)
    entity = media_player.KodiMediaPlayer(device_config, device)

    if api.available_entities.contains(entity.id):
        api.available_entities.remove(entity.id)
    api.available_entities.add(entity)


def on_device_added(device: config.KodiConfigDevice) -> None:
    """Handle a newly added device in the configuration."""
    _LOG.debug("New device added: %s", device)
    _configure_new_device(device, connect=False)


def on_device_removed(device: config.KodiConfigDevice | None) -> None:
    """Handle a removed device in the configuration."""
    if device is None:
        _LOG.debug("Configuration cleared, disconnecting & removing all configured Kodi instances")
        for configured in _configured_kodis.values():
            _LOOP.create_task(_async_remove(configured))
        _configured_kodis.clear()
        api.configured_entities.clear()
        api.available_entities.clear()
    else:
        if device.id in _configured_kodis:
            _LOG.debug("Disconnecting from removed Kodi %s", device.id)
            configured = _configured_kodis.pop(device.id)
            _LOOP.create_task(_async_remove(configured))
            for entity_id in _entities_from_device_id(configured.id):
                api.configured_entities.remove(entity_id)
                api.available_entities.remove(entity_id)


async def _async_remove(device: kodi.KodiDevice) -> None:
    """Disconnect from receiver and remove all listeners."""
    await device.disconnect()
    device.events.remove_all_listeners()


async def main():
    """Start the Remote Two integration driver."""
    logging.basicConfig()

    level = os.getenv("UC_LOG_LEVEL", "DEBUG").upper()
    logging.getLogger("lg").setLevel(level)
    logging.getLogger("discover").setLevel(level)
    logging.getLogger("driver").setLevel(level)
    logging.getLogger("media_player").setLevel(level)
    logging.getLogger("kodi").setLevel(level)
    logging.getLogger("setup_flow").setLevel(level)

    # Load driver config
    config.devices = config.Devices(api.config_dir_path, on_device_added, on_device_removed)
    for device_config in config.devices.all():
        _configure_new_device(device_config, connect=False)

    # _LOOP.create_task(receiver_status_poller())
    for device in _configured_kodis.values():
        if not device.available:
            continue

        # try:
        #     await _LOOP.create_task(device.connect())
        # except WEBOSTV_EXCEPTIONS as ex:
        #     _LOG.debug("Could not connect to device, probably because it is starting with magic packet %s", ex)

    await api.init("driver.json", setup_flow.driver_setup_handler)


if __name__ == "__main__":
    _LOOP.run_until_complete(main())
    _LOOP.run_forever()
