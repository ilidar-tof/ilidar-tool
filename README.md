# iLidar Configuration Tool
Python script used to set up the iTFS sensor and update the firmware.

Available for iTFS firmware version `1.5.0` and later.

## Preparation

- Download the `ilidar-tool.py` script and the `/preset` folder
- Connect the iTFS sensor and your PC. Make sure you know the sensor's destination IP address and port information (sensor's default destination: `192.168.5.2:7256`).

## Usage
### Python script version
```
$ python ilidar-tool.py <command> [arguments ...] [options ...]
```


## List of Commands, Arguments, and Options

### Commands
|            Command            | Description                                                                                                                                                                                                                                                         |
| :---------------------------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|       `-h, --help`        | Prints how to use this script.                                                                                                                                                                                                                                      |
|   `-i, --info <target>`   | Reads the information of connected LiDARs. The read data is saved in the format `/read/info_[date]_[time].json`. <br> If a target is specified, only the information of the target LiDAR is read. <br> To read all the LiDARs, use `all` or `a`.  |
|  `-p, --pause <target>`   | Sets connected LiDARs to pause mode.                                                                                                                                                                                                                                |
| `-m, --measure <target>`  | Sets connected LiDARs to measurement mode.                                                                                                                                                                                                                          |
|   `-l, --lock <target>`   | Locks the configuration locker of connected LiDARs.                                                                                                                                                                                                                 |
|  `-u, --unlock <target>`  | Unlocks the configuration locker of connected LiDARs.                                                                                                                                                                                                               |
|  `-r, --reboot <target>`  | Reboots connected LiDARs.                                                                                                                                                                                                                                           |
| `-d, --redirect <target>` | Redirects the destination IP of connected LiDARs to the current sender's IP.<br> The destination port remains unchanged.                                                                                                                                           |
|    `--reset <target>`     | Restores the LiDAR's parameter settings to the factory default state.<br> **Target arguments are mandatory.**                                                                                                                                                        |
|  `--config <json\|dir>`   | Reads parameter configuration files (`json`), searches for LiDARs on the file, and sets their parameters from the files.<br> To configure many LiDARs, put `dir path` on the argument field. (This will read all files in that directory)                   |
| `--convert <csv> <json>`  | Converts parameter configuration files in `csv` format to `json` format.<br> Both arguments are mandatory.                                                                                                                                              |
|    `--update <target>`    | Reads a firmware file (bin) and updates the firmware of the connected LiDARs with the corresponding firmware file.<br> The firmware file must be located in the `/bin` directory. (For the latest firmware files, please contact the manufacturer, **HYBO Inc.**)        |
|  `--overwrite <target>`   | Performs the same operation as the `--update` command but forces overwriting even if the files has older version.                                                                                                                                               |

### Arguments
|    Argument    | Description                                                                                                                                                                                                                                                                                                              |
| :------------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `<target>` | The IP or serial number of the target sensors.<br> If the target arguments are IP addresses, this script will simply send the command packet.<br> If the target arguments are serial numbers, the script will first search among the connected LiDARs for sensors and then send the command packet to the found sensors.<br> Some commands support `a` and `all`. In this case, the behavior is performed for all sensors that are connected.|
|  `<json>`  | Name of a configuration file in `json` format.                                                                                                                                                                                                                                                                       |
|  `<csv>`   | Name of a configuration file in table format.<br> See example files in the `/preset` directory.                                                                                                                                                                                                                          |

### Options

For hosts with more than one IP address or PORT, the option allows setting only the LiDARs connected to the specific IP and PORT. It means if the option is not used, the default data receiving PORT (`7256`) on all IP addresses (`INADDR_ANY`) will be used in the command.

|           Option           | Description                                                                                                                          |
| :------------------------: | ------------------------------------------------------------------------------------------------------------------------------------ |
|    `-I, --sender <ip>`     | Sets the sender's IP. So, the command will be sent to LiDARs who has the condition: `data_dest_ip == <ip> && data_dest_port == 7256` |
|   `-P, --sender <port>`    | Sets the sender's port. `data_dest_ip == INADDR_ANY && data_dest_port == <port>`                                                     |
| `-S, --sender <ip>:<port>` | Sets the both IP and port of the sender. `data_dest_ip == <ip> && data_dest_port == <port>`                                          |

## Examples

### Quick Reference Table

| Script                                                  | Description                                                                                                                                    |
| :------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `python ilidar-tool.py -i a`                            | Read infomation from all connected LiDARs                                                                                                      |
| `python ilidar-tool.py -p 192.168.5.200 192.168.5.201`  | Set pause mode to LiDARs who has `192.168.5.200` or `192.168.5.201`                                                                            |
| `python ilidar-tool.py -m 456 457`                      | Set measurement mode to LiDARs who has serial number `456` or `457`                                                                            |
| `python ilidar-tool.py -l 458 459 -I 192.168.5.2`       | Lock LiDARs who has serial number `458` or `459` and `data_dest_ip == 192.168.5.2`                                                             |
| `python ilidar-tool.py -u 460 461 -P 17256`             | Unlock LiDARs who has serial number `460` or `461` and `data_dest_port == 17256`                                                               |
| `python ilidar-tool.py -l 460 461 -S 192.168.5.2:17256` | Unlock LiDARs who has serial number `460` or `461` and `data_dest_ip == 192.168.5.2` and `data_dest_port == 17256`                             |
| `python ilidar-tool.py --convert input.csv output.json` | Convert the file `input.csv` to `input.json`                                                                                                   |
| `python ilidar-tool.py --config lidar00.json`           | Configure the LiDAR who has the same serial number in the file `lidar00.json`                                                                  |
| `python ilidar-tool.py --config /preset01`              | Configure all the LiDARs from the files in `/preset01` directory                                                                               |
| `python ilidar-tool.py --update 462`                    | Update the firmware who has serial number `462`. |

### Sender's IP and Port

The `ilidar-tool` uses the `ip address` and `port` defined by the `-s, --sender` option to connect to the iTFS sensor. Therefore, the values of this option must be the same as the `data_dest_ip` and `data_dest_port` of the sensor you want to connect to. If you have a LAN connection with more than 2 lines, we recommend that you always use this option.

- Use specific sender's IP address
  
  `python ilidar-tool.py <command> [arguments ...] -I 192.168.5.2`
- Use specific sender's Port
  
  `python ilidar-tool.py <command> [arguments ...] -P 7256`
- Use specific sender's IP and Port
  
  `python ilidar-tool.py <command> [arguments ...] -S 192.168.5.2:7256`

### Read Information

`-i, --info <target>` reads information from the connected sensor and saves it to the file `/read/info_[date]_[time].json`. `<target>` can contain the sensor's serial number, IP address, `a`, and `all`; `a` and `all` will store information about all connected sensors.

- Read information from serial number 123
  
  `python ilidar-tool.py -i 123`

- Read information from serial number `123` and `124`
  
  `python ilidar-tool.py --info 123 124`

- Read information from IP address `192.168.5.123` and `192.168.5.124`
  
  `python ilidar-tool.py -i 192.168.5.123 192.168.5.124`

### Measure/Pause

After boot, the iTFS sensor is continuously taking measurements and sending data. If you want to pause a measurement, you can do so by sending the command `-p, --pause <target>`. If you want to start measuring again, you can do so by sending the command `-m, --measure <target>`.

- Pause serial number `123`
  
  `python ilidar-tool.py -p 123`

- Pause IP address `192.168.5.123` and `192.168.5.124`
  
  `python ilidar-tool.py --pause 192.168.5.123 192.168.5.124`

- Restart measure serial number `123` and `124`
  
  `python ilidar-tool.py -m 123 124`

### Configuration Lock/Unlock

The iTFS sensor has a built-in configuration lock feature. To put the sensor in a locked state, use the command `-l, --lock <target>`. To unlock it, use the command `-u, --unlock <target>`.

- Lock configuration of serial number `123`
  
  `python ilidar-tool.py -l 123`

- Lock configuration of IP address `192.168.5.123` and `192.168.5.124`
  
  `python ilidar-tool.py --lock 192.168.5.123 192.168.5.124`

- Unlock configuration of serial number `123` and `124`
  
  `python ilidar-tool.py -u 123 124`

### Reboot

To reboot the iTFS sensor, use the command `-r, --reboot <target>`.

- Reboot serial number `123`
  
  `python ilidar-tool.py -r 123`

- Reboot IP address `192.168.5.123` and `192.168.5.124`
  
  `python ilidar-tool.py --reboot 192.168.5.123 192.168.5.124`

### Redirect

Change the received sensor's `data_dest_ip` to the sender's IP address (port is not changed). Used when you are physically connected to a sensor but cannot receive data normally because the sensor's `data_dest_ip` does not match your device. Using a network packet analysis tool, find the IP address of that sensor. Send the command `-d, --redirect <target>` with that IP address as the value of `<target>`.

When using the redirect command, it may not be helpful to include the serial number in the <target> value; it will retrieve the serial number of a sensor that is already communicating normally. **It is recommended to include the IP address explicitly.**

- Redirect IP address `192.168.5.123` and `192.168.5.124` to the sender's IP address

  `python ilidar-tool.py -d 192.168.5.123 192.168.5.124`

### Factory Reset

Factory reset the behavior parameters of the iTFS sensor. The value of <Target> must be explicitly specified as a serial number or IP address.

- Factory reset IP address `192.168.5.123` and `192.168.5.124`
  
  `python ilidar-tool.py --reset 192.168.5.123 192.168.5.124`

### Configuration Sensor

The `--config <json\|dir>` command reads the configuration information specified in <json/dir> and changes the settings of multiple connected sensors simultaneously. To help with this, the `--convert <csv> <json>` command converts a `csv`-formatted configuration file into a `json` file for the `--config` command. To understand sensor configuration using both commands, please follow these steps.

1. Open the file `/preset/default.csv` using a spreadsheet editor. Enter the serial numbers of the connected iTFS sensors in the `sensor_sn` column line by line, deleting any unnecessary rows.
2. Save it.
3. In shell, enter `python ilidar-tool.py --convert /preset/default.csv /preset/default.json`. The `csv` file is then converted to a `json` file.
4. Enter `python ilidar-tool.py --config /preset/default.json -s <sender's IP>:<sender's port>`. `ilidar-tool` will find the sensors corresponding to the serial numbers in the `json` file and change their configurations.
5. Wait for the configuration and reboot to complete, and check the changed settings.

The `--config` command finds the connected sensor based on serial number, so the sensor's `data_dest_ip` and `data_dest_port` values must match the information in senders. 

For more information about the configuration presets, please refer to `/preset/how_to_use_presets.md`.

### Firmware Update

The `--update <target>` and `--overwrite <target>` commands are used for firmware updates. The `--update` command compares the current firmware version of the sensor with the firmware version to be updated, and performs a firmware update if necessary. The `--overwrite` command overwrites the firmware file without comparing versions. Updating the firmware requires the sensor's firmware binary file in the `/bin` folder. 

1. Place the firmware file to be updated inside the `/bin` folder.
2. Enter `python ilidar-tool.py --update <target>`.
3. If it enter the firmware update normally, the following procedure happens automatically: Safe boot → Firmware transfer → Reboot → Start operation.

For the latest firmware files, please contact the manufacturer, **HYBO Inc.**

## Known Issues

#### Infinite wait during firmware update

During a firmware update via `ilidar-tool.py`, `ilidar-tool.py` could get stuck in an infinite wait state. In most cases, forcing a shutdown with `Ctrl+C` and restarting resolves the issue. Specifying user network parameters with `-S` or `--sender` may help prevent the issue.


## License
All example projects are licensed under the MIT License. Copyright 2022-Present HYBO Inc.  
See LICENSE file to check the licenses of all open source libraries used in each project.
