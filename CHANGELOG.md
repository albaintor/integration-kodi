# Kodi integration for Remote Two Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

- Rename the predefined simple commands to match [expected UC name patterns](https://github.com/unfoldedcircle/core-api/blob/main/doc/entities/entity_media_player.md#command-name-patterns)
- Brings support for the different keymaps (e.g by bringing a separator in the command name to set the keymap name)

---

## v1.0.2 - 2024-04-25
### Added remote entity and default mapping
- New remote entity (firmware >= 1.7.10) with support for custom commands and command sequences with repeat, delay, holding time
- Default buttons mapping when raising entity page
- Default interface mapping when raising entity page

## v1.0.0 - 2024-03-16
### Initial release
