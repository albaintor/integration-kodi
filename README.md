# Kodi integration for Remote Two and 3

Using (modified) [pykodi](https://github.com/OnFreund/PyKodi)
and [uc-integration-api](https://github.com/aitatoi/integration-python-library)

The driver lets discover and configure your Kodi instances. A media player and a remote entity are exposed to the core.

Note : this release requires remote firmware `>= 1.7.10`

### Supported attributes
- State (on, off, playing, paused, unknown)
- Title
- Album
- Artist
- Artwork
- Media position / duration
- Volume (level and up/down) and mute
- Remote entity : predefined buttons mapping and interface buttons (to be completed)


### Supported commands for Media Player entity
- Turn off (turn on is not supported)
- Direction pad and enter
- Numeric pad
- Back
- Next
- Previous
- Volume up
- Volume down
- Pause / Play
- Channels Up/Down
- Menus (home, context)
- Colored buttons
- Subtitle/audio language switching
- Fast forward / rewind
- Stop
- Simple commands (more can be added) : see [list of simple commands](#list-of-simple-commands)


### Supported commands for Remote entity
- Send command : custom commands or keyboard commands which sent as KB keymap commands in JSON RPC (see [Kodi keyboard map](https://github.com/xbmc/xbmc/blob/master/system/keymaps/keyboard.xml) and more specifically [Action Ids](https://kodi.wiki/view/Action_IDs) for the list of available keyboard commands)
Example : type in `togglefullscreen` in the command field of the remote entity to toggle full screen 
- Send command sequence (same commands as above)
- Support for the repeat, hold, delay parameters
- List of commands (simple or custom) : see [the list here](#additional-commands)


## Installation

- First [go to the release section](https://github.com/albaintor/integration-kodi/releases) and download the `xxx_aarch64-xxx.tar.gz` file
- On the Web configurator of your remote, go to the `Integrations` tab, click on `Add new` and select `Install custom`
- Select the downloaded file in first step and wait for the upload to finish
- A new integration will appear in the list : click on it and start setup 
- Kodi must be running for setup, and control enabled from Settings > Services > Control section. Set the username, password and enable HTTP control.
<img width="588" alt="image" src="https://github.com/user-attachments/assets/7809d1c7-0be6-4b44-ab9a-73539b58a3f0">

- Port numbers shouldn't be modified normally (8080 for HTTP and 9090 for websocket) : websocket port is not configurable from the GUI (in advanced settings file)
- There is no turn on command : Kodi has to be started some other way
- Change these Kodi settings to get full control working : within Kodi, click settings, then go to `Apps`/`Add-on Browser`, `My Add-ons` and scroll down and click on `Peripheral Libraries` : click on `Joystick Support` and click `Disable`. THEN : kill and restart Kodi in order to take effect and then all the remote commands will work fine
  - This step may not work on Kodi >= 22 : one may have to keep Joystick support enabled and Joystick addon too.


### Hint for saving battery life

To save battery life, the integration will stop reconnecting if Kodi is off (which is the case on most devices when you switch from Kodi to another app).
But if any Kodi command is sent (cursor pad, turn on, play/pause...), a reconnection will be automatically triggered.

So if you start Kodi (ex : from  Nvidia Shield), but you mapped all cursors pad and enter to Nvidia Shield device (through AndroidTV integration or bluetooth), Kodi reconnection won't be triggered.
So here is the trick to make Kodi integration reconnect : create a macro with your devices (e.g. Nvidia Shield, and Kodi media player) with the following commands :
1. Nvidia Shield : `Input Source` command to start app `Kodi`
2. Kodi media player : `Switch On` command (which does nothing except triggering reconnection)

And add the macro to your activity, mapped to the screen or to a button. In that way, it will both launch Kodi and trigger the reconnection.


### Installation on the Remote

- Download the release from the release section : file ending with `.tar.gz`
- Navigate into the Web Configurator of the remote, go into the `Integrations` tab, click on `Add new` and select : `Install custom`
- Select the downloaded `.tar.gz` file and click on upload
- Once uploaded, the new integration should appear in the list : click on it and select `Start setup`
- Your Kodi instance must be running and connected to the network before proceed

### Backup or restore configuration

The integration lets backup or restore the devices configuration (in JSON format).
To use this functionality, select the "Backup or restore" option in the setup flow, then you will have a text field which will be empty if no devices are configured. 
- Backup : just save the content of the text field in a file for later restore and abort the setup flow (clicking next will apply this configuration)
- Restore : just replace the content by the previously saved configuration and click on next to apply it. Beware while using this functionality : the expected format should be respected and could change in the future.
If the format is not recognized, the import will be aborted and existing configuration will remain unchanged.


## Additional commands

First don't mix up with entities : when registering the integration, you will get 2 entities : `Media Player` and `Remote` entities.

The media player entity should cover most needs, however if you want to use custom commands and use additional parameters such as repeating the same command, you can use the remote entity.

This entity exposes 2 specific commands : `Send command` and `Command sequence`

Here is an example of setting a `Send command` command from the remote entity :

<img width="335" height="451" alt="image" src="https://github.com/user-attachments/assets/d3e2e011-7a5d-42fa-bcfe-66e722c6d025" />


### List of simple commands

These are exposed by both media & remote entities :

| Simple command                 | Description                                            |
|--------------------------------|--------------------------------------------------------|
| MENU_VIDEO                     | Show video menu (showvideomenu)                        |
| MODE_TOGGLE_GUI                | Toggle GUI while playing                               |
| MODE_FULLSCREEN                | Toggle full screen (togglefullscreen)                  |
| MODE_SHOW_AUDIO_STREAM         | Show audio streams menu while playing (Kodi >=22)      |
| MODE_SHOW_SUBTITLES_STREAM     | Show subtitles streams menu while playing (Kodi >=22)  |
| MODE_SHOW_AUDIO_MENU           | Show audio context menu while playing                  |
| MODE_SHOW_SUBTITLES_MENU       | Show subtitles context menu while playing              |
| MODE_SHOW_VIDEO_MENU           | Show video settings menu while playing                 |
| MODE_SHOW_BOOKMARKS_MENU       | Show bookmarks menu while playing                      |
| MODE_SHOW_SUBTITLE_SEARCH_MENU | Show subtitles search menu while playing               |
| MODE_SCREENSAVER               | Show screensaver                                       |
| MODE_ZOOM_IN                   | Zoom in (zoomin)                                       |
| MODE_ZOOM_OUT                  | Zoom out (zoomout)                                     |
| MODE_INCREASE_PAR              | Increase aspect ratio (increasepar)                    |
| MODE_DECREASE_PAR              | Decrease aspect ratio (decreasepar)                    |
| MODE_SHOW_SUBTITLES            | Toggle subtitles (showsubtitles)                       |
| MODE_SUBTITLES_DELAY_MINUS     | Decrease subtitles delay (subtitledelayminus)          |
| MODE_SUBTITLES_DELAY_PLUS      | Increase subtitles delay (subtitledelayplus)           |
| MODE_AUDIO_DELAY_MINUS         | Decrease audio delay (audiodelayminus)                 |
| MODE_AUDIO_DELAY_PLUS          | Increase audio delay (audiodelayplus)                  |
| MODE_DELETE                    | Delete (delete)                                        |
| APP_HIBERNATE                  | Hibernate the device (System.Hibernate)                |
| APP_REBOOT                     | Reboot the device (System.Reboot)                      |
| APP_SHUTDOWN                   | Shutdown the device (System.Shutdown)                  |
| APP_SUSPEND                    | Suspend the device (System.Suspend)                    |
| ACTION_BLUE                    | Blue command                                           |
| ACTION_GREEN                   | Green command                                          |
| ACTION_RED                     | Red command                                            |
| ACTION_YELLOW                  | Yellow command                                         |
| System.Hibernate               | Hibernate the device                                   |
| System.Reboot                  | Reboot the device                                      |
| System.Shutdown                | Shutdown the device                                    |
| System.Suspend                 | Suspend the device                                     |



### List of standard commands (remote entity only)

The following commands are standard commands available for the remote entity in addition of simple commands. These are already exposed by the `Media Player` entity through a predefined mappping but can also be used in the remote entity (to build commands sequence for example) :

`on, off, toggle, play_pause, stop, previous, next, fast_forward, rewind, seek, volume, volume_up, volume_down, mute_toggle, mute, unmute, repeat, shuffle, channel_up, channel_down, cursor_up, cursor_down, cursor_left, cursor_right, cursor_enter, digit_0, digit_1, digit_2, digit_3, digit_4, digit_5, digit_6, digit_7, digit_8, digit_9, function_red, function_green, function_yellow, function_blue, home, menu, context_menu, guide, info, back, select_source, select_sound_mode, record, my_recordings, live, eject, open_close, audio_track, subtitle, settings, search`

### List of custom commands (remote entity only)

Additionally, the following custom commands can be set in the `Send command` or `Command sequence` commands of the `Remote` entity.
Some can have parameters


| Custom command                            | Description                                                                                                                | Example                            |
|-------------------------------------------|----------------------------------------------------------------------------------------------------------------------------|------------------------------------|
| activatewindow `windowId`                 | Show the given window ID, [see this link](https://kodi.wiki/view/Window_IDs)                                               | `activatewindow movieinformation`  |
| stereoscopimode `mode`                    | Set the given stereoscopic mode, [see here](https://kodi.wiki/view/JSON-RPC_API/v13#GUI.SetStereoscopicMode)               | `stereoscopimode split_horizontal` |
| viewmode `mode`                           | Set view mode : normal,zoom,stretch4x3,widezoom,stretch16x9,original, stretch16x9nonlin,zoom120width,zoom110width          | `viewmode stretch16x9`             |
| zoom `mode`                               | Set zoom to given mode : in, out or level from 1 to 10                                                                     | `zoom in`                          |
| speed `speed`                             | Set playback speed : increment, decrement or integer from -32, -16, -8,... to 32                                           | `speed 32`                         |
| audiodelay `offset`                       | Set audio delay in seconds relatively                                                                                      | `audiodelay -0.1`                  |
| _&lt;JSON RPC Command&gt; `{parameters}`_ | Any JSON RPC command [complete list here](https://kodi.wiki/view/JSON-RPC_API/v13)<br>_Length is limited to 64 characters_ | _See examples below_               |

#### **Examples of custom commands**

**Execute action : [list of actions here](https://kodi.wiki/view/JSON-RPC_API/v13#Input.Action)**
- Show video menu : `Input.ExecuteAction {"action":"showvideomenu"}`
- Increase subtitles delay : `Input.ExecuteAction {"action":"subtitledelayplus"}`
- Decrease subtitles delay : `Input.ExecuteAction {"action":"subtitledelayminus"}`

**Shutdown the system :**
`System.Shutdown`

**Restart the system :**
`System.Restart`

**Increase audio delay :**
`Player.SetAudioDelay {"playerid":PID,"offset":"increment"}`

**Decrease audio delay :**
`Player.SetAudioDelay {"playerid":PID,"offset":"decrement"}`

**Set audio delay to +0.5 seconds :**
`Player.SetAudioDelay {"playerid":PID,"offset":0.5}`


Notes :
- Some commands require a player Id parameter, just submit `PID` value that will be evaluated on runtime
- Commands length if limited to 64 characters

## Installation as external integration

- Requires Python 3.11
- Under a virtual environment : the driver has to be run in host mode and not bridge mode, otherwise the turn on function won't work (a magic packet has to be sent through network and it won't reach it under bridge mode)
- Your Kodi instance has to be started in order to run the setup flow and process commands. When configured, the integration will detect automatically when it will be started and process commands.
- Install required libraries:  
  (using a [virtual environment](https://docs.python.org/3/library/venv.html) is highly recommended)

```shell
pip3 install -r requirements.txt
```

For running a separate integration driver on your network for Remote Two, the configuration in file
[driver.json](driver.json) needs to be changed:

- Set `driver_id` to a unique value, `uc_kodi_driver` is already used for the embedded driver in the firmware.
- Change `name` to easily identify the driver for discovery & setup with Remote Two or the web-configurator.
- Optionally add a `"port": 8090` field for the WebSocket server listening port.
    - Default port: `9090`
    - Also overrideable with environment variable `UC_INTEGRATION_HTTP_PORT`

### Custom installation

```shell
python3 src/driver.py
```

See
available [environment variables](https://github.com/unfoldedcircle/integration-python-library#environment-variables)
in the Python integration library to control certain runtime features like listening interface and configuration
directory.

## Build self-contained binary for Remote Two

After some tests, turns out python stuff on embedded is a nightmare. So we're better off creating a single binary file
that has everything in it.

To do that, we need to compile it on the target architecture as `pyinstaller` does not support cross compilation.

### x86-64 Linux

On x86-64 Linux we need Qemu to emulate the aarch64 target platform:

```bash
sudo apt install qemu binfmt-support qemu-user-static
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
```

Run pyinstaller:

```shell
docker run --rm --name builder \
    --platform=aarch64 \
    --user=$(id -u):$(id -g) \
    -v "$PWD":/workspace \
    docker.io/unfoldedcircle/r2-pyinstaller:3.11.6  \
    bash -c \
      "python -m pip install -r requirements.txt && \
      pyinstaller --clean --onefile --name driver src/driver.py"
```

### aarch64 Linux / Mac

On an aarch64 host platform, the build image can be run directly (and much faster):

```shell
docker run --rm --name builder \
    --user=$(id -u):$(id -g) \
    -v "$PWD":/workspace \
    docker.io/unfoldedcircle/r2-pyinstaller:3.11.6  \
    bash -c \
      "python -m pip install -r requirements.txt && \
      pyinstaller --clean --onefile --name driver src/driver.py"
```

## Docker Setup (x86-64 & ARM64)

For easy installation on x86-64 and ARM64 systems using Docker:

### Quick Start

```bash
# Clone repository
git clone https://github.com/albaintor/integration-kodi.git
cd integration-kodi

# Start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

### Using Makefile (recommended)

```bash
# Build and start
make start

# View logs  
make logs

# Stop
make down

# Restart
make restart
```

### Using Pre-built Docker Images

```bash
# Pull and run from Docker Hub
docker run -d \
  --name kodi-integration \
  --network host \
  -v $(pwd)/config:/app/config \
  -e UC_INTEGRATION_HTTP_PORT=9090 \
  docker.io/your-username/kodi-integration:latest
```

### Manual Docker Commands

```bash
# Build image locally
docker build -t kodi-integration .

# Run container
docker run -d \
  --name kodi-integration \
  --network host \
  -v $(pwd)/config:/app/config \
  -e UC_INTEGRATION_HTTP_PORT=9090 \
  kodi-integration
```

### Configuration

- Integration runs on port `9090` (configurable via `UC_INTEGRATION_HTTP_PORT`)
- Configuration data is stored in `./config` directory
- `network_mode: host` is required for network discovery and magic packets
- Supports both x86-64 and ARM64 architectures

### Access

After startup, the integration is available at `http://localhost:9090` and can be configured in Remote Two/Three.

### Available Docker Tags

- `latest` - Latest development build from main branch
- `v1.x.x` - Specific version releases
- `main` - Latest commit from main branch

### Docker Hub

Pre-built images are available on Docker Hub with multi-architecture support (x86-64 and ARM64).

## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available, see the
[tags and releases in this repository](https://github.com/albaintor/integration-kodi/releases).

## Changelog

The major changes found in each new release are listed in the [changelog](CHANGELOG.md)
and under the GitHub [releases](https://github.com/albaintor/integration-kodi/releases).

## Contributions

Please read our [contribution guidelines](CONTRIBUTING.md) before opening a pull request.

## License

This project is licensed under the [**Mozilla Public License 2.0**](https://choosealicense.com/licenses/mpl-2.0/).
See the [LICENSE](LICENSE) file for details.


