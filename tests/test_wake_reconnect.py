"""Regression tests for concurrent Kodi connection and standby handling."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from ucapi import StatusCodes

from kodi_device import Events, KodiDevice, retry_call_command


@pytest_asyncio.fixture
async def device():
    """Create a device with a scripted websocket and no network access."""
    config = Mock(id="kodi-test", address="localhost", name="Test Kodi", media_update_task=False)
    instance = KodiDevice(config)
    connection = Mock(connected=False)
    connection.close = AsyncMock(side_effect=lambda: setattr(connection, "connected", False))

    async def initialize():
        instance._kodi_connection = connection

    async def establish():
        connection.connected = True

    connection.connect = AsyncMock(side_effect=establish)
    instance.init_connection = AsyncMock(side_effect=initialize)
    instance._register_callbacks = AsyncMock()
    instance._ping = AsyncMock()
    instance._update_states = AsyncMock()
    instance._media_browser = Mock()
    instance.events.emit = Mock()
    try:
        yield instance, connection
    finally:
        await instance.disconnect()


@pytest.mark.asyncio
async def test_first_command_waits_for_real_reconnection(device):
    kodi, ws = device
    kodi._connection_status = asyncio.get_running_loop().create_future()
    kodi._connection_status.set_result(True)
    started = asyncio.Event()
    allow_connection = asyncio.Event()

    async def establish():
        started.set()
        await allow_connection.wait()
        ws.connected = True

    ws.connect.side_effect = establish
    connect_task = asyncio.create_task(kodi.connect())
    await asyncio.wait_for(started.wait(), 1)
    send = AsyncMock()
    command = asyncio.create_task(retry_call_command(5, False, send, kodi))
    await asyncio.sleep(0)
    send.assert_not_awaited()
    allow_connection.set()
    assert await asyncio.wait_for(connect_task, 1)
    assert await asyncio.wait_for(command, 1) == StatusCodes.OK
    send.assert_awaited_once_with(kodi)


@pytest.mark.asyncio
async def test_parallel_connect_does_not_release_other_tasks_lock(device):
    kodi, ws = device
    started = asyncio.Event()
    release = asyncio.Event()

    async def establish():
        started.set()
        await release.wait()
        ws.connected = True

    ws.connect.side_effect = establish
    first = asyncio.create_task(kodi.connect())
    await asyncio.wait_for(started.wait(), 1)
    assert not await kodi.connect()
    assert kodi._connect_lock.locked()
    assert not await kodi.connect()
    assert ws.connect.await_count == 1
    release.set()
    assert await asyncio.wait_for(first, 1)
    assert not kodi._connect_lock.locked()


@pytest.mark.asyncio
async def test_failed_attempt_does_not_publish_connected(device):
    kodi, ws = device
    ws.connect.side_effect = RuntimeError("network unreachable")
    assert not await kodi.connect()
    assert not kodi.available
    assert not kodi.connection_ready
    assert kodi.connection_status is not None
    assert not kodi.connection_status.done()
    kodi.events.emit.assert_not_called()


@pytest.mark.asyncio
async def test_command_timeout_does_not_send_to_disconnected_socket(device):
    kodi, ws = device
    ws.connect.side_effect = RuntimeError("network unreachable")
    send = AsyncMock()
    assert await retry_call_command(1, False, send, kodi) == StatusCodes.SERVICE_UNAVAILABLE
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_standby_cancels_connect_and_invalidates_old_waiters(device):
    kodi, ws = device
    started = asyncio.Event()
    blocked = asyncio.Event()

    async def establish():
        started.set()
        await blocked.wait()

    ws.connect.side_effect = establish
    connect_task = asyncio.create_task(kodi.connect())
    await asyncio.wait_for(started.wait(), 1)
    send = AsyncMock()
    command = asyncio.create_task(retry_call_command(5, False, send, kodi))
    await asyncio.sleep(0)
    old_status = kodi.connection_status
    await asyncio.wait_for(kodi.disconnect(), 1)

    assert connect_task.cancelled()
    assert await asyncio.wait_for(command, 1) == StatusCodes.SERVICE_UNAVAILABLE
    assert old_status is not None and old_status.result() is False
    assert kodi.connection_status is not old_status
    assert kodi.connection_status is not None and not kodi.connection_status.done()
    assert kodi._websocket_task is None
    assert not kodi._connect_lock.locked()
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_transient_failure_keeps_waiters_for_next_attempt(device):
    kodi, ws = device
    ws.connect.side_effect = RuntimeError("network unreachable")
    send = AsyncMock()
    command = asyncio.create_task(retry_call_command(5, False, send, kodi))
    await asyncio.sleep(0)
    assert kodi._scheduled_connect_task is not None
    assert not await kodi._scheduled_connect_task
    status = kodi.connection_status
    assert status is not None and not status.done()
    send.assert_not_awaited()

    async def establish():
        ws.connected = True

    ws.connect.side_effect = establish
    assert await kodi.connect()
    assert status is kodi.connection_status
    assert await asyncio.wait_for(command, 1) == StatusCodes.OK
    send.assert_awaited_once_with(kodi)
