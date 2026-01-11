"""
Media-player entity functions.

:copyright: (c) 2023 by Unfolded Circle ApS.
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

import logging
from typing import Any

from ucapi import EntityTypes, MediaPlayer, StatusCodes
from ucapi.media_player import Commands, DeviceClasses, Options

import kodi
from config import KodiConfigDevice, KodiEntity, create_entity_id
from const import (
    KODI_ACTIONS_KEYMAP,
    KODI_ADVANCED_SIMPLE_COMMANDS,
    KODI_ALTERNATIVE_BUTTONS_KEYMAP,
    KODI_BUTTONS_KEYMAP,
    KODI_SIMPLE_COMMANDS,
    KODI_SIMPLE_COMMANDS_DIRECT,
    ButtonKeymap,
    MethodCall,
)

_LOG = logging.getLogger(__name__)


class KodiMediaPlayer(KodiEntity, MediaPlayer):
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
        simple_commands = [*list(KODI_SIMPLE_COMMANDS.keys()), *list(KODI_ADVANCED_SIMPLE_COMMANDS.keys())]
        simple_commands.sort()
        options = {Options.SIMPLE_COMMANDS: simple_commands}
        super().__init__(
            entity_id, config_device.name, features, attributes, device_class=DeviceClasses.RECEIVER, options=options
        )

    @property
    def deviceid(self) -> str:
        """Return device identifier."""
        return self._device.id

    @staticmethod
    async def mediaplayer_command(
        entity_id: str, device: kodi.KodiDevice, cmd_id: str, params: dict[str, Any] | None = None
    ) -> StatusCodes:
        """Handle any command for Media Player and Remote entities."""
        # pylint: disable=R0915
        if device is None:
            _LOG.warning("No Kodi instance for entity: %s", entity_id)
            return StatusCodes.SERVICE_UNAVAILABLE
        if params is None:
            params = {}

        # Occurs when the user press a button after wake up from standby and
        # the driver reconnection is not triggered yet
        if not device.kodi_connection or not device.kodi_connection.connected:
            await device.connect()

        if cmd_id == Commands.VOLUME:
            res = await device.set_volume_level()
        elif cmd_id == Commands.VOLUME_UP:
            res = await device.volume_up()
        elif cmd_id == Commands.VOLUME_DOWN:
            res = await device.volume_down()
        elif cmd_id == Commands.MUTE_TOGGLE:
            res = await device.mute(not device.is_volume_muted)
        elif cmd_id == Commands.MUTE:
            res = await device.mute(True)
        elif cmd_id == Commands.UNMUTE:
            res = await device.mute(False)
        elif cmd_id == Commands.ON:
            res = await device.power_on()
        elif cmd_id == Commands.OFF:
            res = await device.power_off()
        elif cmd_id == Commands.NEXT:
            res = await device.next()
        elif cmd_id == Commands.PREVIOUS:
            res = await device.previous()
        elif cmd_id == Commands.PLAY_PAUSE:
            res = await device.play_pause()
        elif cmd_id == Commands.STOP:
            res = await device.stop()
        elif cmd_id == Commands.HOME:
            res = await device.home()
        elif cmd_id == Commands.SETTINGS:
            res = await device.call_command("GUI.ActivateWindow", **{"window": "settings"})
        elif cmd_id == Commands.CONTEXT_MENU:
            res = await device.context_menu()
        elif cmd_id == Commands.SEEK:
            res = await device.seek(params.get("media_position", 0))
        elif cmd_id == Commands.SETTINGS:
            res = await device.call_command("GUI.ActivateWindow", **{"window": "screensaver"})
        elif cmd_id == Commands.SELECT_SOURCE:
            res = await device.select_chapter(params.get("source"))
        elif cmd_id == Commands.SELECT_SOUND_MODE:
            res = await device.select_audio_track(params.get("mode"))
        elif not device.device_config.disable_keyboard_map and cmd_id in KODI_BUTTONS_KEYMAP:
            command: ButtonKeymap | MethodCall = KODI_BUTTONS_KEYMAP[cmd_id]
            if "button" in command.keys():
                command: ButtonKeymap = command.copy()
                hold = params.get("hold", 0)
                if hold != "" and hold > 0:
                    command["holdtime"] = hold
                res = await device.command_button(command)
            else:
                command: MethodCall = command
                res = await device.call_command(command["method"], **command["params"])
        elif device.device_config.disable_keyboard_map and cmd_id in KODI_ALTERNATIVE_BUTTONS_KEYMAP:
            command: MethodCall = KODI_ALTERNATIVE_BUTTONS_KEYMAP[cmd_id]
            res = await device.call_command(command["method"], **command["params"])
        elif cmd_id in KODI_ACTIONS_KEYMAP:
            res = await device.command_action(KODI_ACTIONS_KEYMAP[cmd_id])
        elif cmd_id in KODI_SIMPLE_COMMANDS:
            command = KODI_SIMPLE_COMMANDS[cmd_id]
            if command in KODI_SIMPLE_COMMANDS_DIRECT:
                res = await device.call_command(command)
            else:
                res = await device.command_action(command)
        elif cmd_id in KODI_ADVANCED_SIMPLE_COMMANDS:
            command: MethodCall | str = KODI_ADVANCED_SIMPLE_COMMANDS[cmd_id]
            if isinstance(command, str):
                command: str = command
                res = await device.command_action(command)
            else:
                command: MethodCall = command
                res = await device.call_command(command["method"], **command["params"])
        else:
            return await KodiMediaPlayer.custom_command(device, cmd_id)
        return res

    @staticmethod
    async def custom_command(device: kodi.KodiDevice, command: str) -> StatusCodes:
        """Handle custom commands for Media Player and Remote entities."""
        # pylint: disable=R0911,R0915
        arguments = command.split(" ", 1)
        command_key = arguments[0].lower()
        if command_key == "activatewindow" and len(arguments) == 2:
            arguments = {"window": arguments[1]}
            _LOG.debug("[%s] Custom command GUI.ActivateWindow %s", device.device_config.address, arguments)
            return await device.call_command("GUI.ActivateWindow", **arguments)
        if command_key == "stereoscopimode" and len(arguments) == 2:
            arguments = {"mode": arguments[1]}
            _LOG.debug("[%s] Custom command GUI.SetStereoscopicMode %s", device.device_config.address, arguments)
            return await device.call_command("GUI.SetStereoscopicMode", **arguments)
        if command_key == "viewmode" and len(arguments) == 2:
            return await device.view_mode(arguments[1])
        if command_key == "zoom" and len(arguments) == 2:
            mode = arguments[1]
            if mode not in ["in", "out"]:
                try:
                    mode = int(mode)
                except ValueError:
                    pass
            return await device.zoom(mode)
        if command_key == "speed" and len(arguments) == 2:
            value = arguments[1]
            if value not in ["increment", "decrement"]:
                try:
                    value = int(value)
                except ValueError:
                    pass
            return await device.speed(value)
        if command_key == "audiodelay" and len(arguments) == 2:
            value = arguments[1]
            try:
                value = float(value)
            except ValueError:
                pass

            return await device.audio_delay(value)
        if command_key == "key" and len(arguments) == 2:
            value = arguments[1]
            value = value.split(" ")
            button: ButtonKeymap = ButtonKeymap(button=value[0], keymap="KB", holdtime=0)
            if len(value) >= 2:
                button["keymap"] = value[1]
            if len(value) == 3:
                try:
                    button["holdtime"] = int(value[2])
                except ValueError:
                    pass
            _LOG.debug(
                "[%s] Keyboard command Input.ButtonEvent %s %s %s",
                device.device_config.address,
                button["button"],
                button["keymap"],
                button["holdtime"],
            )
            return await device.command_button(button)
        if command_key == "action" and len(arguments) == 2:
            value = arguments[1]
            _LOG.debug("[%s] Action command Input.ExecuteAction %s", device.device_config.address, value)
            return await device.call_command_args("Input.ExecuteAction", value)
        params = {}
        try:
            # Evaluate arguments from custom command and create necessary variables (PID)
            if len(arguments) == 2:
                # pylint: disable=C0103,W0123,W0612
                PID = 1  # noqa: F841
                if "PID" in arguments[1]:
                    PID = device.player_id  # noqa: F841
                params = eval(arguments[1])
        # pylint: disable = W0718
        except Exception as ex:
            _LOG.error("[%s] Custom command bad arguments : %s %s", device.device_config.address, arguments[1], ex)
        _LOG.debug("[%s] Custom command : %s %s", device.device_config.address, command, params)
        return await device.call_command(command_key, **params)

    async def command(self, cmd_id: str, params: dict[str, Any] | None = None, *, websocket: Any) -> StatusCodes:
        """
        Media-player entity command handler.

        Called by the integration-API if a command is sent to a configured media-player entity.

        :param cmd_id: command
        :param params: optional command parameters
        :param websocket: optional websocket connection. Allows for directed event
                          callbacks instead of broadcasts.
        :return: status code of the command request
        """
        _LOG.info("Got %s command request: %s %s", self.id, cmd_id, params)
        return await KodiMediaPlayer.mediaplayer_command(self.id, self._device, cmd_id, params)
