# Unlim8ted OS Documentation

## Overview

**Unlim8ted OS** is a lightweight phone-style operating environment for the **CM4 phone project**, built around a Raspberry Pi Compute Module 4 stack. The repository is structured like an OS overlay or filesystem payload rather than a conventional application repo: it contains boot configuration, service definitions, a Python backend, a browser-rendered UI shell, app modules, and JSON-backed persistent state.

At a high level, the system boots on CM4 hardware, starts a Python backend as a systemd service, and presents a custom touch-friendly interface rendered in Chromium. The backend exposes local HTTP endpoints used by the frontend for system control, app launching, media access, and state synchronization.

## Project Goals

The CM4 phone project uses this repository to provide:

- A custom phone-like interface for CM4-based hardware
- Hardware-aware boot and display configuration
- Local app hosting and app switching
- Camera support for the CM4 carrier setup
- Persistent state for system settings and app data
- A simple architecture that is easy to iterate on

This is not a full Linux distribution by itself. It is the **Unlim8ted OS layer** that sits on top of an existing Raspberry Pi OS style base image.

## Repo Structure

- [`./boot/firmware/config.txt`](./boot/firmware/config.txt) contains CM4 display and camera baseline boot configuration.
- [`./etc/systemd/system/unlim8ted.service`](./etc/systemd/system/unlim8ted.service) starts the Python backend on boot.
- [`./etc/default/unlim8ted`](./etc/default/unlim8ted) contains runtime environment overrides for display output names, browser path, and backlight path.
- [`./opt/unlim8ted/backend/main.py`](./opt/unlim8ted/backend/main.py) is the local HTTP backend.
- [`./opt/unlim8ted/ui/index.html`](./opt/unlim8ted/ui/index.html) and [`./opt/unlim8ted/ui/app.js`](./opt/unlim8ted/ui/app.js) provide the shell UI.
- [`./opt/unlim8ted/apps/`](./opt/unlim8ted/apps/) contains the built-in app modules.
- [`./opt/unlim8ted/commands/registry.json`](./opt/unlim8ted/commands/registry.json) documents user-facing command endpoints.

## Base Image Expectations

Unlim8ted OS expects to be layered onto a Raspberry Pi OS style base image with:

- Python 3 available at `/usr/bin/python3`
- Chromium available at `/usr/bin/chromium-browser`
- A graphical session on `:0`
- systemd enabled
- CM4 display, touch, and camera support packages installed

This repo does not currently build the base image for you. Treat it as an overlay that gets copied onto a prepared device image.

## Installation

### 1. Prepare the base system

Start from a working Raspberry Pi OS image for the CM4 hardware. Before copying this overlay, confirm the following on the device:

- The CM4 boots normally from the selected storage
- The Waveshare display shows Linux output
- Touch input works at the desktop level
- Chromium launches manually
- The connected camera is visible to `libcamera`

### 2. Copy the overlay onto the device

Copy the contents of this `os/` directory onto the root filesystem of the Pi image so the paths land exactly as laid out in the repo:

- `boot/firmware/config.txt` -> `/boot/firmware/config.txt`
- `etc/default/unlim8ted` -> `/etc/default/unlim8ted`
- `etc/systemd/system/unlim8ted.service` -> `/etc/systemd/system/unlim8ted.service`
- `opt/unlim8ted/...` -> `/opt/unlim8ted/...`
- `root/.vnc/...` -> `/root/.vnc/...` if you are using the included root desktop session setup

If you are merging into an existing image instead of replacing files wholesale, review the target files first and merge carefully rather than overwriting unrelated local changes.

### 3. Review boot configuration

Check [`./boot/firmware/config.txt`](./boot/firmware/config.txt) against the actual hardware:

- `dtoverlay=vc4-kms-v3d` enables the KMS graphics stack
- `dtoverlay=imx219,cam0` assumes an IMX219 camera on CAM0
- `gpu_mem=256` reserves enough memory for Chromium and camera preview

If the final camera module, display stack, or GPU requirements differ, adjust this file before first boot.

### 4. Review runtime configuration

Edit [`./etc/default/unlim8ted`](./etc/default/unlim8ted) for the target device:

- `UNLIM8TED_BROWSER` should point to the installed Chromium binary
- `UNLIM8TED_DISPLAY` should match the graphical session display, usually `:0`
- `UNLIM8TED_XAUTHORITY` should match the X session authority file
- `UNLIM8TED_WLR_OUTPUT` and `UNLIM8TED_XRANDR_OUTPUT` should match the real output name on the device
- `UNLIM8TED_BACKLIGHT_PATH` should match the real backlight brightness sysfs path

The default values are a reasonable CM4 starting point, but they should be verified on hardware instead of assumed.

### 5. Enable the service

After the overlay is in place on the Pi:

```bash
sudo systemctl daemon-reload
sudo systemctl enable unlim8ted.service
sudo systemctl restart unlim8ted.service
```

The service definition lives at [`./etc/systemd/system/unlim8ted.service`](./etc/systemd/system/unlim8ted.service) and launches the backend with root privileges.

## First-Boot Verification

Use this order so failures stay isolated:

1. Confirm the base OS still boots after the overlay is applied.
2. Check that the display comes up and the graphical session is on the expected output.
3. Verify the backend starts: `systemctl status unlim8ted.service`
4. If the service fails, inspect logs: `journalctl -u unlim8ted.service -b`
5. Open Chromium manually once if needed and confirm the UI shell loads from the local backend.
6. Test brightness and sleep/wake actions from the UI.
7. Confirm camera preview and capture work with the configured module.

## Bring-Up Checklist

Before calling the image stable, verify all of the following on device:

- The backend starts automatically on boot
- The UI renders without requiring a keyboard or mouse
- Touch input is correctly mapped to the display orientation
- Brightness control writes to the configured backlight path
- Sleep and wake behave predictably
- The camera preview opens without blocking the rest of the shell
- Captured media lands in the expected runtime state location
- App launch and app switching work across the built-in apps

## Development Notes

This repo contains both source files and local runtime artifacts. Generated runtime data such as Chromium profile state, captured media, logs, and Python bytecode should not be committed as source of truth. The top-level `.gitignore` is intended to keep those paths out of normal version control flow.

For day-to-day work, keep code and deployable defaults in the repo, but treat device-specific runtime state as disposable.
