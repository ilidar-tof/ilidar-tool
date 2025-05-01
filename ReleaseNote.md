# iLidar Tool Release Notes


## Introduction

1. This document describes the software updates for the `iLidar Tool`.
2. For further details on the softwares, please contact **json@hybo.co** or **jungingyo@hybo.co**.


## Change Log

### [V1.1.9] - 2025-05-01

- Added
  - Added preset files for single or multiple sensors configuration 

### [V1.1.8] - 2025-04-29

- Added
  - Added the release note file for version tracking

- Issues
  - Firmware update infinite wait
    - `ilidar-tool.py` can get stuck in an infinite wait during the firmware update process
    - In most cases, force quitting with `Ctrl+C` and restarting solves the problem
    - Alternatively, specifying user network information using the `-S` or `--sender` option can prevent the problem

### [V1.1.7] - 2025-04-18 (Initial Public Commit)

- Added
  - Python-based iTFS sensor management tool
  - Read and write parameters, or change the sensor's operational state

### [V1.1.6]

- Fixed
  - invalid option error in --convert
  - indexing error in update process was fixed

### [V1.1.5]

- Changed
  - modify ethernet interface searching function using 'ip 4 addr' command
  - update option formats for multiple ethernet interface capability
- Added
  - add multiple ip, port and both handling features

### [V1.1.4]

- Added
  - display warning code when use internal loopback ip address

### [V1.1.2]

- Added
  - add an empty item handle function empty to change only the parameters of interest
  - add new example preset files

### [V1.1.1]

- Fixed
  - fix subnet mask error on ubuntu with 'ifconfig' command

### [V1.1.0]

- Intial release version of united `ilidar-tool.py`