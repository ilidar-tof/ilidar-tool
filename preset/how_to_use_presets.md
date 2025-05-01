# iLidar Multiple Sensor Solution Preset Files

Preset files for sensor configuration.
Available for firmware version `1.5.0` and later.

## Usage

1. Open the preset file (**CSV format**) using a tool that supports **CSV editing**.  
2. Modify the **sensor_sn** field to match the **serial number** of the sensor you want to use.
3. Erase unused rows in the field.
4. Save the **CSV** file.  
5. Convert the **CSV** file into a **JSON** configuration file using **ilidar-tool.py**:  
   ```bash
   $ python ilidar-tool.py --convert /preset/mode1.csv cfg_250203.json
   ```
6. Apply the **configuration** to the sensor using **ilidar-tool.py**:  
   ```bash
   $ python ilidar-tool.py --config cfg_250203.json
   ```

## **Preset Files**  

- **default.csv**: Example file for a single sensor.  
- **mode1.csv**: Example file for **MODE1** operation with **up to 28 sensors at 10 Hz**.  
- **mode2.csv**: Example file for **MODE2** operation with **up to 20 sensors at 12.5 Hz**.  
