# iLidar Tool Release Notes


## Introduction

1. This document describes the software updates for the `iLidar Tool`.
2. For further details on the softwares, please contact **json@hybo.co** or **jungingyo@hybo.co**.


## Change Log

### [V1.1.8] - 2025-04-29

- Added
  - Added the release note file for version tracking

- Issues
  - Firmware update infinite wait
    - `ilidar_tool.py` can get stuck in an infinite wait during the firmware update process
    - In most cases, force quitting with `Ctrl+C` and restarting solves the problem
    - Alternatively, specifying user network information using the `-S` or `--sender` option can prevent the problem

### [V1.1.7] - 2025-04-18 (Initial Commit)

- Added
  - Python-based iTFS sensor management tool
  - Read and write parameters, or change the sensor's operational state