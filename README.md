# Unlim8ted Phone

A CM4-based handheld phone project with hardware, 3D, PCB, and OS work in one repo.

![Unlim8ted Phone components animation](https://raw.githubusercontent.com/Unlim8ted-Studio-Productions/unlim8ted-phone/refs/heads/main/3d/Components.gif)

## Repo Layout

    /
    ├─ 3d/        # enclosure, mechanical, renders, printable parts
    ├─ os/        # Unlim8ted OS source and OS-specific docs
    ├─ pcb/       # archived PCB design files from an abandoned revision
    └─ README.md

## Overview

Unlim8ted Phone is a custom handheld phone build based on the Raspberry Pi Compute Module 4. This repo contains the full project. 
It includes:

- hardware documentation
- mechanical / 3D files
- archived PCB files
- software / OS files
- build notes

## Main Parts

- Raspberry Pi Compute Module 4 Lite, 8GB RAM
- Waveshare CM4-NANO-C
- Waveshare 6.25-inch DSI LCD
- 32GB microSD card
- 15cm double-sided 15-pin DSI cable
- Seeed LiPo Rider Plus
- 3.7V 3000mAh LiPo battery
- Adafruit USB Type A to USB Type C cable

## Cost Breakdown

> Prices may change over time.  
> This section reflects the current working build estimate for this project.

| Part | Qty | Price |
|---|---:|---:|
| Raspberry Pi CM4 Lite 8GB | 1 | $105.00 |
| Waveshare CM4-NANO-C | 1 | $29.99 |
| Waveshare 6.25-inch DSI LCD | 1 | $59.99 |
| Seeed LiPo Rider Plus | 1 | $4.90 |
| 3.7V 3000mAh battery | 1 | $12.49 |
| 32GB microSD card | 1 | $20.00 |
| Adafruit USB A to USB C cable (PID 4472) | 1 | $2.95 |
| 15cm DSI cable | 1 | Included with display |

### Current known total

**$235.32**  
Note that this includes the **CM4** 8GB RAM varient which is not necessarily required.

> Final total will be a little higher with the enclosure materials, fasteners, tools, and shipping.

## Important PCB Note

The PCB files in this repo are **archived only**.

The original custom PCB work was **abandoned** and replaced with **already manufactured boards** instead. The files in `/pcb` are kept for reference only and **should NOT be used** for fabrication, ordering, or assembly.

If you are building this project, use the currently selected off-the-shelf/manufactured boards listed in the hardware section instead of the abandoned PCB design files.

## Build Status

This project is still in active development. The repo is being organized so hardware, PCB, 3D, and OS work can all live together.

## Build Instructions

### 1. Gather the parts

At minimum, you need:

- CM4 Lite
- CM4-NANO-C carrier
- Waveshare 6.25-inch DSI LCD
- microSD card (min 12 GB)
- LiPo Rider Plus
- 3.7V battery (min of around 2A to help prevent quick degradation)
- USB-C power/data cable
- 15cm DSI cable
- case and mounting hardware as needed (case is 3D printed) 

### 2. Prepare the microSD card

- Flash the OS image to the 32GB microSD card
- Insert the card into the CM4-NANO-C TF/microSD slot
- Make sure the image matches the current hardware setup

### 3. Install the CM4

- Align the CM4 with the carrier board connectors
- Press it in evenly
- Do not force it
- Double-check full seating before powering anything

### 4. Connect the display

- Connect the 15cm 15-pin DSI cable between the CM4-NANO-C and the Waveshare 6.25-inch DSI LCD
- Verify cable orientation before locking the connectors
- If the display requires additional power or touch connections, wire those before closing the build

### 5. Connect power

- Connect the battery to the LiPo Rider Plus
- Connect the LiPo Rider Plus output to the phone power path
- Connect the USB cable to the charging/input side as needed
- Verify voltage and polarity before first power-on

### 6. First boot

- Power on the board
- Confirm the CM4 boots from microSD
- Confirm the display initializes
- Confirm the OS reaches its main UI or setup state

### 7. Mechanical assembly

Once the electronics boot correctly:

- install everything into the enclosure
- route the battery safely
- secure the display
- mount the PCB/carrier stack
- check cable bend radius and connector strain
- close the case only after a successful powered test

## Recommended Bring-Up Order

To avoid debugging too many things at once:

1. Boot CM4 + carrier + microSD only
2. Add display and confirm video output
3. Add battery/power board
4. Add enclosure/mechanical parts
5. Add remaining peripherals and refinements

## Folders

### `/3d`

3D models, enclosure parts, renders, and printable/mechanical files.

### `/pcb`

Archived PCB design files from an abandoned revision. These files are kept for reference only and **should NOT be used**.

### `/os`

Unlim8ted OS files and OS-specific documentation.

## Notes

- The CM4 used in this project is the **Lite** version, so storage is provided by the microSD card rather than onboard eMMC.
- This repo is meant to track the full phone build, not only the operating system.
- The cost section should be updated as parts change.
- The PCB folder does not represent the current hardware path for this project.

## Links

- OS docs: [`./os/`](./os)
- 3D files: [`./3d/`](./3d)
- PCB files: [`./pcb/`](./pcb)
