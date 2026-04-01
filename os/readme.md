# Unlim8ted OS Documentation

## Overview

**Unlim8ted OS** is a lightweight phone-style operating environment for the **CM4 phone project**, built around a Raspberry Pi Compute Module 4 stack. The repository is structured like an OS overlay or filesystem payload rather than a conventional application repo: it contains boot configuration, service definitions, a Python backend, a browser-rendered UI shell, app modules, and JSON-backed persistent state.

At a high level, the system boots on CM4 hardware, starts a Python backend as a systemd service, and presents a custom touch-friendly interface rendered in Chromium. The backend exposes local HTTP endpoints used by the frontend for system control, app launching, media access, and state synchronization.

---

## Project Goals

The CM4 phone project uses this repository to provide:

- A custom phone-like interface for CM4-based hardware
- Hardware-aware boot and display configuration
- Local app hosting and app switching
- Camera support for the CM4 carrier setup
- Persistent state for system settings and app data
- A simple architecture that is easy to iterate on

This is not a full Linux distribution by itself. It is the **Unlim8ted OS layer** that sits on top of an existing Raspberry Pi OS–style base image.