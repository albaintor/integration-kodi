"""
Test connection script for Kodi integration driver.

:copyright: (c) 2025 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

# pylint: disable=all
# flake8: noqa

import asyncio
import io
import json
import logging
import queue
import sys
from asyncio import Queue, Task, Future, AbstractEventLoop
from contextlib import suppress
from typing import Any, Callable

from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType
from rich import print_json
import tkinter as tk
from tkinter import ttk
import requests
from PIL import Image, ImageTk
import threading


def load_image_from_url(url: str, max_size=(500, 500)) -> ImageTk.PhotoImage:
    # Télécharge l'image
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()

    # Ouvre l'image depuis les bytes
    img = Image.open(io.BytesIO(resp.content))

    # Optionnel : redimensionne pour rentrer dans la fenêtre
    img.thumbnail(max_size)

    return ImageTk.PhotoImage(img)


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)

# address = "192.168.1.60"  # PC
# address = "192.168.1.45"  # Mac
address = "192.168.1.20"  # Shield
username = "kodi"
password = "ludi"

DRIVER_URL = "ws://192.168.1.60:9091/ws"
MAIN_WS_MAX_MSG_SIZE = 8 * 1024 * 1024  # 8Mb
WS_TIMEOUT = 5


class RemoteWebsocket:

    def __init__(self, loop: AbstractEventLoop | None = None):
        self.client_session: ClientSession | None = None
        self.client_websocket: ClientWebSocketResponse | None = None
        self._rx_tasks = set()
        self._id = 0
        self.callback_queues: dict[str, Queue[dict[str, Any]]] = {}
        self.callback_tasks: dict[int, Task] = {}
        self.futures: dict[int, Future[dict[str, Any]]] = {}
        self._loop = loop if loop else asyncio.get_event_loop()

    async def websocket_connect(self):
        self.client_session = ClientSession()
        async with asyncio.timeout(5):
            self.client_websocket = await self.client_session.ws_connect(
                DRIVER_URL,
                heartbeat=5,
                ssl=False,
                max_msg_size=MAIN_WS_MAX_MSG_SIZE,
            )
        if self.client_websocket is None:
            _LOG.error("Websocket connection failed")
            return
        self._rx_tasks.add(asyncio.create_task(self._rx_msgs_main_ws(self.client_websocket)))
        # await asyncio.wait(self._rx_tasks, return_when=asyncio.FIRST_COMPLETED)

    async def disconnect(self):
        await self._closeout_tasks()

    async def get_driver_vertion(self):
        try:
            response = await self.send_request_and_wait(
                {"msg": "get_driver_version"},
                timeout=WS_TIMEOUT,
            )
            return response
        except asyncio.TimeoutError:
            _LOG.error("Timeout while extracting driver version")
            return None

    async def get_entity_states(self):
        try:
            response = await self.send_request_and_wait(
                {"msg": "get_entity_states"},
                timeout=WS_TIMEOUT,
            )
            return response
        except asyncio.TimeoutError:
            _LOG.error("Timeout while extracting entities states")
            return None

    async def subscribe_entities(self, entity_ids: list[str]):
        try:
            response = await self.send_request_and_wait(
                {"msg": "subscribe_events", "msg_data": {"entity_ids": entity_ids}},
                timeout=WS_TIMEOUT,
            )
            return response
        except asyncio.TimeoutError:
            _LOG.error("Timeout while subscribing entities")
            return None

    async def get_available_entities(self):
        try:
            response = await self.send_request_and_wait(
                {"msg": "get_available_entities"},
                timeout=WS_TIMEOUT,
            )
            return response
        except asyncio.TimeoutError:
            _LOG.error("Timeout while getting available entities")
            return None

    def subscribe_events(self, event_type: str, callback: Callable):
        uid = self._id
        self._id += 1
        self._create_subscription_handler(uid, event_type, callback)

    async def send_command(self, command: dict[str, Any]):
        # {"kind":"req","id":35,"msg":"entity_command","msg_data":{"cmd_id":"on","entity_id":"media_player.192.168.1.20","entity_type":"media_player","params":{}}}
        try:
            response = await self.send_request_and_wait(
                {"msg": "entity_command", "msg_data": command},
                timeout=WS_TIMEOUT,
            )
            return response
        except asyncio.TimeoutError:
            _LOG.error("Timeout while sending command")
            return None

    async def _rx_msgs_main_ws(self, web_socket: ClientWebSocketResponse) -> None:
        """Receive messages from main websocket connection."""
        async for raw_msg in web_socket:
            _LOG.debug("receive: %s", raw_msg)
            if raw_msg.type is not WSMsgType.TEXT:
                break

            self._process_text_message(raw_msg.data)

    async def _handle_auth(self):
        # {"kind": "event", "msg": "auth_required","msg_data": {"name":"my-integration","version":{"api":"0.5.0","driver":"1.0.0"}}}
        await self._send_json(
            {"kind": "resp", "req_id": self._id, "code": 200, "msg": "authentication", "msg_data": {}}
        )
        self._id += 1

    async def _send_json(self, msg: dict) -> None:
        _LOG.debug("Send json: %s", msg)
        await self.client_websocket.send_json(msg)

    async def send_request_and_wait(
        self,
        msg: dict,
        timeout: float = 5.0,
    ) -> dict[str, Any] | None:
        """
        Envoie une requête et attend la réponse associée au req_id.
        """
        req_id = self._id
        self._id += 1

        msg["id"] = req_id
        msg["kind"] = "req"

        future = self._loop.create_future()
        self.futures[req_id] = future

        await self._send_json(msg)

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            pass
        finally:
            try:
                # Nettoyage dans tous les cas
                await self.futures.pop(req_id, None)
            except KeyError:
                pass

    def _process_text_message(self, data: str) -> None:
        """Process text message."""
        msg = json.loads(data)
        msg_type = msg.get("msg", "")
        if msg_type == "auth_required":
            asyncio.create_task(self._handle_auth())

        kind = msg.get("kind", "")
        if kind == "event" and (callback_queue := self.callback_queues.get(msg_type)):
            callback_queue.put_nowait(msg)
        else:
            uid = msg.get("req_id", None)
            if uid is None:
                return
            if future := self.futures.get(uid):
                future.set_result(msg)

    @staticmethod
    async def callback_handler(
        handler_queue: Queue[dict[str, Any]],
        callback: Callable,
        future: Future[dict[str, Any]],
    ) -> None:
        """Handle callbacks."""
        with suppress(asyncio.CancelledError):
            while True:
                msg = await handler_queue.get()
                # payload = msg.get("payload")
                try:
                    await callback(msg)
                except Exception as ex:
                    _LOG.error("Exception in callback: %s", ex)
                    pass
                if not future.done():
                    future.set_result(msg)

    def _create_subscription_handler(self, uid: int, msg_type: str, callback: Callable) -> None:
        """Create a subscription handler for a given uid.

        Create a queue to store the messages, a task to handle the messages
        and a future to signal first subscription update processed.
        """
        self.futures[uid] = future = self._loop.create_future()
        subscription_queue: Queue[dict[str, Any]] = asyncio.Queue()
        self.callback_queues[msg_type] = subscription_queue
        self.callback_tasks[uid] = asyncio.create_task(self.callback_handler(subscription_queue, callback, future))

    async def _delete_subscription_handler(self, uid: int, msg_type: str) -> None:
        """Delete a subscription handler for a given id."""
        task = self.callback_tasks.pop(uid)
        if not task.done():
            task.cancel()
        while not task.done():
            with suppress(asyncio.CancelledError):
                await task
        del self.callback_queues[msg_type]

    def _cancel_tasks(self) -> None:
        """Cancel all tasks."""
        for callback_task in self.callback_tasks.values():
            if not callback_task.done():
                callback_task.cancel()

        for task in self._rx_tasks:
            if not task.done():
                task.cancel()

        for future in self.futures.values():
            future.cancel()

    async def close_client_session(self) -> None:
        await self.client_session.close()
        self.client_session = None

    async def _closeout_tasks(self) -> None:
        """Cancel all tasks and close connections."""
        closeout = set()
        self._cancel_tasks()
        if callback_tasks := set(self.callback_tasks.values()):
            closeout.update(callback_tasks)
        closeout.update(self._rx_tasks)
        closeout.add(asyncio.create_task(self.close_client_session()))
        if not closeout:
            return
        closeout_task = asyncio.create_task(asyncio.wait(closeout))
        while not closeout_task.done():
            with suppress(asyncio.CancelledError):
                await asyncio.shield(closeout_task)


class RemoteInterface(tk.Tk):

    def __init__(self) -> None:
        super().__init__()
        self.title("Remote Interface")
        self.geometry("800x600")
        self.ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self.container = ttk.Frame(self, padding=12)
        self.container.pack(fill="both", expand=True)
        self.title_field = ttk.Label(self.container, text="Title")
        self.title_field.pack(anchor="w", pady=(0, 10))
        self.artist = ttk.Label(self.container, text="Artist")
        self.artist.pack(anchor="w", pady=(0, 30))
        self.state = ttk.Label(self.container, text="State")
        self.state.pack(anchor="w", pady=(0, 50))
        self.loop = asyncio.get_running_loop()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(50, self.poll_queue)
        self.photo: tk.PhotoImage | None = None
        self.image_label: ttk.Label | None = None

    def on_close(self):
        self.destroy()

    def poll_queue(self):
        try:
            while True:
                action = self.ui_queue.get_nowait()
                action()
        except Exception:  # queue.Empty:
            pass
        self.after(50, self.poll_queue)

    def load_image(self, url: str) -> None:
        try:
            _LOG.debug("Loading new image from URL: %s", url)
            self.photo = load_image_from_url(url)
            if self.image_label is None:
                self.image_label = ttk.Label(self.container)
                self.image_label.pack(anchor="w")
            self.image_label.configure(image=self.photo)
            self.update()
        except Exception as e:
            error_label = ttk.Label(self.container, text=f"Erreur de chargement de l'image : {e}")
            error_label.pack(anchor="w")

    def set_title(self, title: str) -> None:
        self.title_field["text"] = title
        self.update()

    def set_artist(self, artist: str) -> None:
        self.artist["text"] = artist
        self.update()

    def set_state(self, state: str) -> None:
        self.state["text"] = state
        self.update()


class WorkerThread(threading.Thread):

    def __init__(self, interface: RemoteInterface) -> None:
        super().__init__(daemon=True)
        self._interface = interface
        self._loop: AbstractEventLoop | None = None
        self._loop_ready = threading.Event()
        # self.start()

    def run(self):
        self._loop = asyncio.new_event_loop()
        self._loop_ready.set()
        self._loop.create_task(self.launch_server())
        try:
            self._loop.run_forever()
        finally:
            # 5) Nettoyage: annule toutes les tâches restantes
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.close()

    async def entity_changed(self, msg: dict[str, Any]) -> None:
        _LOG.debug("Entity changed : %s", msg)
        updated_data = msg.get("msg_data", None)
        if updated_data is None:
            return
        print_json(json=json.dumps(msg))
        if "attributes" not in updated_data:
            return
        attributes = updated_data["attributes"]
        if updated_data.get("entity_type", "") != "media_player":
            return
        if "media_image_url" in attributes:
            self._interface.ui_queue.put(lambda u=attributes["media_image_url"]: self._interface.load_image(u))
        if "media_title" in attributes:
            self._interface.ui_queue.put(lambda u=attributes["media_title"]: self._interface.set_title(u))
        if "media_artist" in attributes:
            self._interface.ui_queue.put(lambda u=attributes["media_artist"]: self._interface.set_artist(u))
        if "state" in attributes:
            self._interface.ui_queue.put(lambda u=attributes["state"]: self._interface.set_state(u))

    async def launch_server(self):
        _LOG.debug("Start connection")
        ws = RemoteWebsocket(self._loop)
        ws.subscribe_events("entity_change", self.entity_changed)
        await ws.websocket_connect()
        await asyncio.sleep(1)
        data = await ws.get_driver_vertion()
        _LOG.debug("Driver version : %s", data)
        data = await ws.get_available_entities()
        _LOG.debug("Available entities : %s", data)
        entity_ids: list[str] = []
        for entity in data["msg_data"]["available_entities"]:
            entity_ids.append(entity["entity_id"])
        data = await ws.subscribe_entities(entity_ids)
        _LOG.debug("Subscribed entities : %s", data)
        await asyncio.sleep(5)
        data = await ws.send_command(
            {"cmd_id": "on", "entity_id": "media_player.192.168.1.60", "entity_type": "media_player", "params": {}}
        )
        _LOG.debug("Command result : %s", data)
        data = await ws.get_entity_states()
        _LOG.debug("Entities states : %s", data)
        # await asyncio.sleep(600)
        # await ws.disconnect()


async def main():
    interface = RemoteInterface()
    worker: WorkerThread = WorkerThread(interface)
    worker.start()
    interface.mainloop()


if __name__ == "__main__":
    _LOG = logging.getLogger(__name__)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logging.basicConfig(handlers=[ch])
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    logging.getLogger("client").setLevel(logging.DEBUG)
    logging.getLogger("media_player").setLevel(logging.DEBUG)
    logging.getLogger("remote").setLevel(logging.DEBUG)
    logging.getLogger("kodi").setLevel(logging.DEBUG)
    logging.getLogger("pykodi.kodi").setLevel(logging.DEBUG)

    logging.getLogger(__name__).setLevel(logging.DEBUG)
    _LOOP.run_until_complete(main())
    _LOOP.run_forever()
