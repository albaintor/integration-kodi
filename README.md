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
- Simple commands (more can be added) : video menu, toggle fullscreen, zoom in/out, increase/decrease aspect ratio, toggle subtitles, subtitles delay minus/plus, audio delay minus/plus


### Supported commands for Remote entity
- Send command : commands are sent as KB keymap commands in JSON RPC (see [Kodi keyboard map](https://github.com/xbmc/xbmc/blob/master/system/keymaps/keyboard.xml) for the list of available commands)
- Send command sequence (same commands as above)
- Support for the repeat, hold, delay parameters
- Simple commands : the same as media player simple commands, with the addition of the other media player commands


## Installation

- Kodi must be running for setup, and control enabled from Settings > Services > Control section. Set the username, password and enable HTTP control.
<img width="588" alt="image" src="https://github.com/user-attachments/assets/7809d1c7-0be6-4b44-ab9a-73539b58a3f0">
- Port numbers shouldn't be modified normally (8080 for HTTP and 9090 for websocket) : websocket port is not configurable from the GUI (in advanced settings file)
- There is no turn on command : Kodi has to be started some other way
- Change these Kodi settings to get full control working : within Kodi, click settings, then go to `Apps`/`Add-on Browser`, `My Add-ons` and scroll down and click on `Peripheral Libraries` : click on `Joystick Support` and click `Disable`. THEN : kill and restart Kodi in order to take effect and then all the remote commands will work fine


### Important hint

To spare battery life, the integration will stop reconnecting if Kodi is off (which is the case on most devices when you switch from Kodi to another app). 
But if any Kodi command is sent (cursor pad, turn on, play/pause...), a reconnection will be automatically triggered.
So if you start Kodi from for example your Nvidia Shield but you mapped all cursors pad and enter to Nvidia Shield device (through AndroidTV integration or bluetooth), Kodi reconnection won't be triggered.
So here is the trick to make Kodi integration reconnect : create a macro with your devices (e.g. Nvidia Shield, and Kodi media player) with the following commands :
1. Nvidia Shield : `Input Source` command to start app `Kodi`
2. Kodi media player : `Switch On` command (which does nothing except triggering reconnection)

And add the macro to your activity, mapped to the screen or to a button. In that way, it will both launch Kodi and trigger the reconnection.


### Installation on the Remote (recommended)

- Download the release from the release section : file ending with `.tar.gz`
- Navigate into the Web Configurator of the remote, go into the `Integrations` tab, click on `Add new` and select : `Install custom`
- Select the downloaded `.tar.gz` file and click on upload
- Once uploaded, the new integration should appear in the list : click on it and select `Start setup`
- Your TV must be running and connected to the network before proceed

### Backup or restore configuration

The integration lets backup or save the devices configuration.
To use this functionality, select the "Backup or restore" option in the setup flow, then you will have a text field which will be empty if no devices are configured. You just have to replace the content by the previously saved configuration and click on next to apply it. Beware while using this functionality : the expected format should be respected and could change in the future.
If the format is not recognized, the import will be aborted and existing configuration will remain unchanged.


### Installation as external integration

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

### Run

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


