##
# @file ilidar-tool.py
# @brief Python script for HYBO iLidar-ToF sensors
# @note Run this script with -h or --help to see how to use this
# @author JSon (json@hybo.co) JeongIngyo(jungingyo@hybo.co)
# @date 2025-04-18
#

#### MODULE IMPORT ####
import os
import sys
import socket
import subprocess
import time
import argparse
import ipaddress
import csv
import json

from enum import Enum
from datetime import datetime

if os.name == "nt":
    import msvcrt
else:
    import select


#### CONSTANT ####
# Script version
ilidar_tool_version = "1.1.7"   # Version of this script
# V 1.1.0   Intial release version of united ilidar-tool.py
# V 1.1.1   Fixed
#            - fix subnet mask error on ubuntu with 'ifconfig' command
# V 1.1.2   Added
#            - add an empty item handle function empty to change only the parameters of interest
#            - add new example preset files
# V 1.1.4   Added
#            - display warning code when use internal loopback ip address
# V 1.1.5   Changed
#            - modify ethernet interface searching function using 'ip -4 addr' command
#            - update option formats for multiple ethernet interface capability
#           Added
#            - add multiple ip, port and both handling features
# V 1.1.6   Fixed
#            - invalid option error in --convert
#            - indexing error in update process was fixed
# V 1.1.7   Fixed
#            - invalid sockConfig changed to sock['config']


#### LOCAL FUNCTION DEFINITIONS ####
# Path function
def get_executable_path():
    # return PyInstaller exe file
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)  # Path of PyInstaller EXE file
    return os.path.dirname(__file__)  # Path of Script

# Encode function of info_2 packet for F/W V1.5.0+
def encode_info_v2(src):
    dst = bytearray(166)  # 166-byte array

    # Sensor serial number (16-bit)
    dst[0] = src['sensor_sn'] % 256
    dst[1] = src['sensor_sn'] // 256

    # Fill bytes 2 to 68 with 0 (Read only in original code)
    for i in range(2, 70):
        dst[i] = 0

    # Capture mode and capture row (8-bit values)
    dst[71] = src['capture_mode']
    dst[72] = src['capture_row']

    # Capture shutter (16-bit values, total 5 elements)
    for i in range(5):
        dst[73 + i * 2] = (src['capture_shutter'][i] >> 0) & 0xFF
        dst[74 + i * 2] = (src['capture_shutter'][i] >> 8) & 0xFF

    # Capture limit (16-bit values, total 2 elements)
    dst[83] = (src['capture_limit'][0] >> 0) & 0xFF
    dst[84] = (src['capture_limit'][0] >> 8) & 0xFF
    dst[85] = (src['capture_limit'][1] >> 0) & 0xFF
    dst[86] = (src['capture_limit'][1] >> 8) & 0xFF

    # Capture period (32-bit value)
    dst[87] = (src['capture_period_us'] >> 0) & 0xFF
    dst[88] = (src['capture_period_us'] >> 8) & 0xFF
    dst[89] = (src['capture_period_us'] >> 16) & 0xFF
    dst[90] = (src['capture_period_us'] >> 24) & 0xFF

    # Capture sequence (8-bit value)
    dst[91] = src['capture_seq']

    # Data output and baud rate (32-bit value)
    dst[92] = src['data_output']
    dst[93] = (src['data_baud'] >> 0) & 0xFF
    dst[94] = (src['data_baud'] >> 8) & 0xFF
    dst[95] = (src['data_baud'] >> 16) & 0xFF
    dst[96] = (src['data_baud'] >> 24) & 0xFF

    # Sensor and destination IP addresses (each 4 bytes)
    dst[97:101] = src['data_sensor_ip']
    dst[101:105] = src['data_dest_ip']
    dst[105:109] = src['data_subnet']
    dst[109:113] = src['data_gateway']

    # Data port (16-bit value)
    dst[113] = (src['data_port'] >> 0) & 0xFF
    dst[114] = (src['data_port'] >> 8) & 0xFF

    # MAC address (6 bytes)
    dst[115:121] = src['data_mac_addr']

    # Sync configuration
    dst[121] = src['sync']
    dst[122] = (src['sync_trig_delay_us'] >> 0) & 0xFF
    dst[123] = (src['sync_trig_delay_us'] >> 8) & 0xFF
    dst[124] = (src['sync_trig_delay_us'] >> 16) & 0xFF
    dst[125] = (src['sync_trig_delay_us'] >> 24) & 0xFF

    # Sync illumination delay (16-bit values, total 15 elements)
    for i in range(15):
        dst[126 + i * 2] = (src['sync_ill_delay_us'][i] >> 0) & 0xFF
        dst[127 + i * 2] = (src['sync_ill_delay_us'][i] >> 8) & 0xFF

    # Sync trimmer values (8-bit)
    dst[156] = src['sync_trig_trim_us']
    dst[157] = src['sync_ill_trim_us']

    # Sync output delay (16-bit)
    dst[158] = (src['sync_output_delay_us'] >> 0) & 0xFF
    dst[159] = (src['sync_output_delay_us'] >> 8) & 0xFF

    # Arbitration settings (8-bit and 32-bit)
    dst[160] = src['arb']
    dst[161] = (src['arb_timeout'] >> 0) & 0xFF
    dst[162] = (src['arb_timeout'] >> 8) & 0xFF
    dst[163] = (src['arb_timeout'] >> 16) & 0xFF
    dst[164] = (src['arb_timeout'] >> 24) & 0xFF

    # Additional flag
    dst[165] = 0  # This flag is not written in the info packet

    return dst

# Decode function of info_v2 packet for F/W V1.5.0+
def decode_info_v2(src):
    # Initialize the output dictionary
    dst = {}
    dst['ilidar_version'] = "1.5.X"

    # Sensor serial number (16-bit)
    dst['sensor_sn'] = (src[1] << 8) | src[0]

    # Sensor HW ID (30 bytes)
    dst['sensor_hw_id'] = src[2:32]

    # Sensor FW version (3 bytes)
    dst['sensor_fw_ver'] = src[32:35]

    # Sensor FW date (12 bytes)
    dst['sensor_fw_date'] = src[35:47]

    # Sensor FW time (9 bytes)
    dst['sensor_fw_time'] = src[47:56]

    # Sensor calibration ID (32-bit)
    dst['sensor_calib_id'] = (src[59] << 24) | (src[58] << 16) | (src[57] << 8) | src[56]

    # Sensor firmware versions (3 bytes each)
    dst['sensor_fw0_ver'] = src[60:63]
    dst['sensor_fw1_ver'] = src[63:66]
    dst['sensor_fw2_ver'] = src[66:69]

    # Sensor model and boot control (8-bit values)
    dst['sensor_model_id'] = src[69]
    dst['sensor_boot_ctrl'] = src[70]

    # Capture mode and row (8-bit)
    dst['capture_mode'] = src[71]
    dst['capture_row'] = src[72]

    # Capture shutter (16-bit values, total 5 elements)
    dst['capture_shutter'] = [
        (src[74] << 8) | src[73],
        (src[76] << 8) | src[75],
        (src[78] << 8) | src[77],
        (src[80] << 8) | src[79],
        (src[82] << 8) | src[81]
    ]

    # Capture limit (16-bit values, total 2 elements)
    dst['capture_limit'] = [
        (src[84] << 8) | src[83],
        (src[86] << 8) | src[85]
    ]

    # Capture period (32-bit value)
    dst['capture_period_us'] = (src[90] << 24) | (src[89] << 16) | (src[88] << 8) | src[87]

    # Capture sequence (8-bit value)
    dst['capture_seq'] = src[91]

    # Data output (8-bit value)
    dst['data_output'] = src[92]

    # Data baud rate (32-bit value)
    dst['data_baud'] = (src[96] << 24) | (src[95] << 16) | (src[94] << 8) | src[93]

    # Sensor and destination IP addresses (4 bytes each)
    dst['data_sensor_ip'] = src[97:101]
    dst['data_dest_ip'] = src[101:105]
    dst['data_subnet'] = src[105:109]
    dst['data_gateway'] = src[109:113]

    # Data port (16-bit value)
    dst['data_port'] = (src[114] << 8) | src[113]

    # Data MAC address (6 bytes)
    dst['data_mac_addr'] = src[115:121]

    # Sync settings (8-bit and 32-bit values)
    dst['sync'] = src[121]
    dst['sync_trig_delay_us'] = (src[125] << 24) | (src[124] << 16) | (src[123] << 8) | src[122]

    # Sync illumination delay (16-bit values, total 15 elements)
    dst['sync_ill_delay_us'] = [
        (src[127] << 8) | src[126],
        (src[129] << 8) | src[128],
        (src[131] << 8) | src[130],
        (src[133] << 8) | src[132],
        (src[135] << 8) | src[134],
        (src[137] << 8) | src[136],
        (src[139] << 8) | src[138],
        (src[141] << 8) | src[140],
        (src[143] << 8) | src[142],
        (src[145] << 8) | src[144],
        (src[147] << 8) | src[146],
        (src[149] << 8) | src[148],
        (src[151] << 8) | src[150],
        (src[153] << 8) | src[152],
        (src[155] << 8) | src[154]
    ]

    # Sync trim and delay (8-bit and 16-bit values)
    dst['sync_trig_trim_us'] = src[156]
    dst['sync_ill_trim_us'] = src[157]
    dst['sync_output_delay_us'] = (src[159] << 8) | src[158]

    # Arbitration (8-bit and 32-bit values)
    dst['arb'] = src[160]
    dst['arb_timeout'] = (src[164] << 24) | (src[163] << 16) | (src[162] << 8) | src[161]

    # Lock (8-bit value)
    dst['lock'] = src[165]

    return dst

# Overwrite function of info_v2 packet for F/W V1.5.0+
def overwrite_info_v2(src, dst):
    common_keys = src.keys() & dst.keys()
    overwritten_keys = []
    for key in common_keys:
        if dst[key] == '':
            dst[key] = src[key]
            overwritten_keys.append(key)
    return overwritten_keys

# Get a list of bin files in the current directory
def get_bin_files(directory):
    bin_files = [f for f in os.listdir(directory) if f.endswith('.bin')]
    return sorted(bin_files)

# Read the info from each bin file
def read_bin_files(bin_files):
    bin_files_and_info = []

    # List all files in the directory
    for bin_file in bin_files:
        # Split the filename using the underscore '_' as the delimiter
        parts = bin_file.split('_')
        if len(parts) == 7:
            id_part = parts[6].split('.')
            id = id_part[0]
            bin_data = {}
            bin_data['file_name'] = bin_file
            bin_data['fw_type'] = parts[1]
            bin_data['fw_version'] = [int(parts[4]), int(parts[3]), int(parts[2])]
            bin_data['sensor_sn'] = int(parts[5])
            bin_data['sensor_id'] = id
            bin_data['sensor_id_arr'] = [int(id[i:i+2], 16) for i in range(2, len(id), 2)]

            bin_files_and_info.append(bin_data)
    
    return bin_files_and_info

# Manual flush function for socket
def flush_socket(sock):
    while True:
        try:
            data = sock.recv(2000)
            if not data:
                break
        except OSError:
            break
        except socket.timeout:
            continue

def cidr_to_subnet(cidr):
    mask = (0xFFFFFFFF >> (32 - cidr)) << (32 - cidr)
    return ".".join(map(str, [(mask >> i) & 0xFF for i in (24, 16, 8, 0)]))

# Get IP list
def get_ip_list():
    if os.name == "nt":
        ip_addresses = []
        
        # Use ipconfig to get all IPs
        result = subprocess.run(['ipconfig'], stdout=subprocess.PIPE, text=True)
        
        # Parse the output to find IP addresses
        lines = result.stdout.splitlines()
        for line in lines:
            if 'IPv4' in line:
                ip = line.split(':')[1].replace(' ', '')
                if ip != '127.0.0.1' and ip not in ip_addresses:
                    ip_addresses.append(ip)
        
        return ip_addresses
    else:
        ip_addresses = []

        # Use ip addr to get all IPs
        result = subprocess.run(['ip', '-4', 'addr'], stdout=subprocess.PIPE, text=True)

        # Parse the output to find IP addresses
        lines = result.stdout.splitlines()
        for line in lines:
            if 'inet ' in line:
                ip = line.strip().split()[1].split('/')[0]
                if ip != '127.0.0.1' and ip not in ip_addresses:
                    ip_addresses.append(ip)
        
        return ip_addresses

# IP check
def is_ip(str):
    try:
        ipaddress.IPv4Address(str)
        return True
    except ValueError:
        return False

# Get subnet mask
def get_subnet_mask(ip):
    if os.name == "nt":
        # Use ipconfig to get all IPs
        result = subprocess.run(['ipconfig'], stdout=subprocess.PIPE, text=True)
        
        # Parse the output to find IP addresses
        lines = result.stdout.splitlines()
        found_idx = -1
        for line_idx, line in enumerate(lines, start=1):
            if 'IPv4' in line:
                host_ip = line.split(':')[1].replace(' ', '')
                if ip == host_ip:
                    found_idx = line_idx
            
            if line_idx == found_idx + 1:
                host_subnet = line.split(':')[1].replace(' ', '')
                return host_subnet
        
        return ''
    else:
        # Use ip addr to get all IPs
        result = subprocess.run(['ip', '-4', 'addr'], stdout=subprocess.PIPE, text=True)

        # Parse the output to find IP addresses
        lines = result.stdout.splitlines()
        for line_idx, line in enumerate(lines, start=1):
            if 'inet' in line:
                host_ip = line.strip().split()[1].split('/')[0]
                host_subnet_cidr = line.strip().split()[1].split('/')[1]
                host_subnet = cidr_to_subnet(int(host_subnet_cidr))
                if ip == host_ip:
                    return host_subnet

        return ''

# Get broadcast ip
def get_broadcast_ip(ip, subnet):
    # Convert IP and subnet mask to IPv4 objects
    network = ipaddress.IPv4Network(f'{ip}/{subnet}', strict=False)
    
    # Get the broadcast address from the network object
    broadcast_address = network.broadcast_address
    return str(broadcast_address)

# Check the same subnet
def is_in_subnet(target_ip, subnet_ip, subnet_mask):
    subnet = ipaddress.ip_network(f"{subnet_ip}/{subnet_mask}", strict=False)
    return ipaddress.ip_address(target_ip) in subnet

# Detect enter press
def is_enter_pressed():
    if os.name == "nt":
        # Windows: Use msvcrt to detect keypress
        if msvcrt.kbhit():  # Check if a key was pressed
            key = msvcrt.getch().decode()
            if key == '\n' or key == '\r':  # Newline or carriage return (Enter key)
                return True
        return False
    else:
        # Unix-like: Use sys.stdin with select and termios for non-blocking input
        if select.select([sys.stdin, ], [], [], 0.0)[0]:  # Non-blocking check
            key = sys.stdin.read(1)  # Read a single character
            if key == '\n' or key == '\r':  # Newline or carriage return (Enter key)
                return True
        return False

# CRC-16 CCITT lookup table
CRC16Table = [
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
    0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef,
    0x1231, 0x0210, 0x3273, 0x2252, 0x52b5, 0x4294, 0x72f7, 0x62d6,
    0x9339, 0x8318, 0xb37b, 0xa35a, 0xd3bd, 0xc39c, 0xf3ff, 0xe3de,
    0x2462, 0x3443, 0x0420, 0x1401, 0x64e6, 0x74c7, 0x44a4, 0x5485,
    0xa56a, 0xb54b, 0x8528, 0x9509, 0xe5ee, 0xf5cf, 0xc5ac, 0xd58d,
    0x3653, 0x2672, 0x1611, 0x0630, 0x76d7, 0x66f6, 0x5695, 0x46b4,
    0xb75b, 0xa77a, 0x9719, 0x8738, 0xf7df, 0xe7fe, 0xd79d, 0xc7bc,
    0x48c4, 0x58e5, 0x6886, 0x78a7, 0x0840, 0x1861, 0x2802, 0x3823,
    0xc9cc, 0xd9ed, 0xe98e, 0xf9af, 0x8948, 0x9969, 0xa90a, 0xb92b,
    0x5af5, 0x4ad4, 0x7ab7, 0x6a96, 0x1a71, 0x0a50, 0x3a33, 0x2a12,
    0xdbfd, 0xcbdc, 0xfbbf, 0xeb9e, 0x9b79, 0x8b58, 0xbb3b, 0xab1a,
    0x6ca6, 0x7c87, 0x4ce4, 0x5cc5, 0x2c22, 0x3c03, 0x0c60, 0x1c41,
    0xedae, 0xfd8f, 0xcdec, 0xddcd, 0xad2a, 0xbd0b, 0x8d68, 0x9d49,
    0x7e97, 0x6eb6, 0x5ed5, 0x4ef4, 0x3e13, 0x2e32, 0x1e51, 0x0e70,
    0xff9f, 0xefbe, 0xdfdd, 0xcffc, 0xbf1b, 0xaf3a, 0x9f59, 0x8f78,
    0x9188, 0x81a9, 0xb1ca, 0xa1eb, 0xd10c, 0xc12d, 0xf14e, 0xe16f,
    0x1080, 0x00a1, 0x30c2, 0x20e3, 0x5004, 0x4025, 0x7046, 0x6067,
    0x83b9, 0x9398, 0xa3fb, 0xb3da, 0xc33d, 0xd31c, 0xe37f, 0xf35e,
    0x02b1, 0x1290, 0x22f3, 0x32d2, 0x4235, 0x5214, 0x6277, 0x7256,
    0xb5ea, 0xa5cb, 0x95a8, 0x8589, 0xf56e, 0xe54f, 0xd52c, 0xc50d,
    0x34e2, 0x24c3, 0x14a0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
    0xa7db, 0xb7fa, 0x8799, 0x97b8, 0xe75f, 0xf77e, 0xc71d, 0xd73c,
    0x26d3, 0x36f2, 0x0691, 0x16b0, 0x6657, 0x7676, 0x4615, 0x5634,
    0xd94c, 0xc96d, 0xf90e, 0xe92f, 0x99c8, 0x89e9, 0xb98a, 0xa9ab,
    0x5844, 0x4865, 0x7806, 0x6827, 0x18c0, 0x08e1, 0x3882, 0x28a3,
    0xcb7d, 0xdb5c, 0xeb3f, 0xfb1e, 0x8bf9, 0x9bd8, 0xabbb, 0xbb9a,
    0x4a75, 0x5a54, 0x6a37, 0x7a16, 0x0af1, 0x1ad0, 0x2ab3, 0x3a92,
    0xfd2e, 0xed0f, 0xdd6c, 0xcd4d, 0xbdaa, 0xad8b, 0x9de8, 0x8dc9,
    0x7c26, 0x6c07, 0x5c64, 0x4c45, 0x3ca2, 0x2c83, 0x1ce0, 0x0cc1,
    0xef1f, 0xff3e, 0xcf5d, 0xdf7c, 0xaf9b, 0xbfba, 0x8fd9, 0x9ff8,
    0x6e17, 0x7e36, 0x4e55, 0x5e74, 0x2e93, 0x3eb2, 0x0ed1, 0x1ef0
]

# CRC16 function
def get_crc16(packet):
    # Use CRC-16 CCITT standard
    crc = 0xFFFF
    for byte in packet:
        crc = (crc << 8) ^ CRC16Table[(crc >> 8) ^ byte]
        crc &= 0xFFFF  # Ensure crc is within 16 bits
    return crc

# Check command error
def check_command(argv):
    # Initial argv checker
    if len(argv) < 2:
        print("Run the script with -h or --help to see the description like:")
        print("  $ python " + argv[0] + " --help")
        return False
    
    # Invalid command checker
    commands = [s for s in argv[1:] if s.startswith('-')]
    commands = [s for s in commands if '-S' not in s]
    commands = [s for s in commands if '-I' not in s]
    commands = [s for s in commands if '-P' not in s]
    if len(commands) > 1:
        print("Invalid command")
        print("Run the script with -h or --help to see the description like:")
        print("  $ python " + argv[0] + " --help")
        return False
    
    return True

# Get command
def get_command(args):
    for a in parser._actions:
        if getattr(args, a.dest) is not None:
            command = a.dest
            arg_list = getattr(args, a.dest)
            return command, arg_list

    return '', None

# Parse arg list
def parse_arg_list(arg_list):
    type_list = []
    data_list = []
    if 'a' in arg_list or 'all' in arg_list:
        type_list.append('ALL')
        data_list.append(0)
        print('    + ALL')
        return type_list, data_list, len(type_list)
    
    for arg in arg_list:
        if is_ip(arg):
            type_list.append('IP')
            data_list.append(arg)
            print('    + IP  ' + arg)
        elif arg.isdigit():
            if int(arg) < 0 or int(arg) > 65535:
                print('    - SN  ' + arg + ' is not in the valid range. (skipped)')
            else:
                type_list.append('SN')
                data_list.append(int(arg))
                print('    + SN  ' + arg)
        else:
            print('    - INV ' + arg + ' does not a target (skipped)')

    print('    ' + str(len(type_list)) + ' targets were found.')
    return type_list, data_list, len(type_list)

# Parse cvt file list
def parse_cvt_list(arg_list):
    file_list = []
    
    csv_found = False
    csv_name = []
    json_name = []
    for arg in arg_list:
        if csv_found == False and arg.endswith('.csv'):
            dir_path = os.getcwd()
            if arg.startswith('/') == False:
                dir_path = dir_path + '/'
            if os.path.exists(dir_path + arg):
                csv_found = True
                csv_name = arg
                file_list.append(dir_path + arg)
                print('    + CSV   ' + arg)
            else:
                print('    - CSV   ' + arg + ' does not exist. (skipped)')
        elif csv_found == True and arg.endswith('.json'):
            dir_path = os.getcwd()
            if arg.startswith('/') == False:
                dir_path = dir_path + '/'
            json_name = arg
            file_list.append(dir_path + arg)
            print('    + JSON  ' + arg)
        else:
            print('    - INV   ' + arg + ' unknown. (skipped)')
    
    if len(file_list) == 2:
        print('    ' + csv_name + ' will be converted to ' + json_name + '.')
        return file_list, len(file_list)
    else:
        return [], 0

# Parse json file list
def parse_json_list(arg_list):
    file_list = []
    
    for arg in arg_list:
        if arg.endswith('.json'):
            dir_path = os.getcwd()
            if arg.startswith('/') == False:
                dir_path = dir_path + '/'
            if os.path.exists(dir_path + arg):
                file_list.append(dir_path + arg)
                print('    + JSON  ' + arg)
            else:
                print('    - JSON  ' + arg + ' does not exist. (skipped)')
        else:
            dir_path = os.getcwd()
            if arg.startswith('/') == False:
                dir_path = dir_path + '/'
            dir_path = dir_path + arg
            if os.path.isdir(dir_path):
                print('    + DIR   ' + arg)
                for f in os.listdir(dir_path):
                    if f.endswith('.json'):
                        file_list.append(dir_path + '/' + f)
                        print('    + JSON  ' + arg + '/' + f)
            else:
                print('    - INV   ' + arg + ' does not exist. (skipped)')
    
    print('    ' + str(len(file_list)) + ' files were found.')
    return file_list, len(file_list)

# Check option error
def check_option(arg):
    ip = ''       # default
    port = 7256   # default
    option_arg = arg.split(':')
    if len(option_arg) == 1:
        if len(option_arg[0].split('.')) == 4 and is_ip(option_arg[0]):
            ip = option_arg[0]
        elif len(option_arg[0].split('.')) == 1 and option_arg[0].isdigit():
            port = int(option_arg[0])
        else:
            # print('Invalid option argument: ' + arg)
            # print('See how to use the script with --help command')
            return False, ip, port
    elif len(option_arg) == 2 and is_ip(option_arg[0]) and option_arg[1].isdigit():
        ip = option_arg[0]
        port = int(option_arg[1])
    else:
        # print('Invalid option argument: ' + arg)
        # print('See how to use the script with --help command')
        return False, ip, port

    host_ip_list = get_ip_list()
    if ip != '' and ip not in host_ip_list:
        # print('Invalid option argument IP: ' + ip)
        # print('The IP is not in the list: ' + str(host_ip_list))
        return False, ip, port

    if port < 0 or port > 65535:
        # print('Invalid option argument range: ' + str(port))
        # print('The port number is not in the range (0 ~ 65535)')
        return False, ip, port
    
    return True, ip, port

# Custom help
class custom_help_action(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        print("                                                                                ")
        print("Usage:                                                                          ")
        print("  Script version:                                                               ")
        print("    $ python ilidar-tool.py command [arguments ...] [options ...]               ")
        print("  Binary version:                                                               ")
        print("    >ilidar-tool.exe command [arguments ...] [options ...]                      ")
        print("    $ ./ilidar-tool command [arguments ...] [options ...]                       ")
        print("                                                                                ")
        print("Command:                                                                        ")
        print("  -h, --help                         Prints how to use this script.             ")
        print("  -i, --info <target>                Reads the information of connected LiDARs. ")
        print("                                     If a target is specified, only the         ")
        print("                                     information of the target LiDAR is read.   ")
        print("                                     To read all the LiDARs, use 'all' or 'a'.  ")
        print("                                     (This type of target setting is available  ")
        print("                                     for all commands unless otherwise noted)   ")
        print("  -p, --pause <target>               Sets connected LiDARs to pause mode.       ")
        print("  -m, --measure <target>             Sets connected LiDARs to measurement mode. ")
        print("  -l, --lock <target>                Locks the configuration locker of connected")
        print("                                     LiDARs.                                    ")
        print("  -u, --unlock <target>              Unlocks the configuration locker of        ")
        print("                                     connected LiDARs.                          ")
        print("  -r, --reboot <target>              Reboots connected LiDARs.                  ")
        print("  -d, --redirect <target>            Redirects the destination IP of connected  ")
        print("                                     LiDARs to the current commander IP.        ")
        print("                                     The destination port remains unchanged.    ")
        print("  --reset <target>                   Restores the LiDAR's parameter settings to ")
        print("                                     the factory default state.                 ")
        print("                                     Target arguments are mandatory.            ")
        print("  --config <json|dir>                Reads parameter configuration files (json),")
        print("                                     searches for LiDARs on the file,           ")
        print("                                     and sets their parameters from the files.  ")
        print("                                     To configure many LiDARs, put dir path on  ")
        print("                                     the argument field. (This will read all    ")
        print("                                     files in that directory)                   ")
        print("  --convert <csv> <json>             Converts parameter configuration files     ")
        print("                                     in csv format to json format.              ")
        print("                                     Arguments are mandatory.                   ")
        print("  --update <target>                  Reads a firmware file (bin) and updates the")
        print("                                     firmware of the connected LiDARs with the  ")
        print("                                     corresponding firmware file.               ")
        print("                                     The firmware file must be located in the   ")
        print("                                     '/bin' directory.                          ")
        print("                                     (For the latest firmware files,            ")
        print("                                     please contact the manufacturer, HYBO)     ")
        print("  --overwrite <target>               Performs the same operation as the         ")
        print("                                     '--update' command but forces overwriting  ")
        print("                                     even if the files has older version.       ")
        print("                                                                                ")
        print("Argument:                                                                       ")
        print("  <target>       The IP or serial number of the target sensors.                 ")
        print("                 If the target arguments are IP addresses, this script will     ")
        print("                 simply send the command packet.                                ")
        print("                 If the target arguments are serial numbers, the script will    ")
        print("                 first search among the connected LiDARs for sensors and then   ")
        print("                 send the command packet to the found sensors.                  ")
        print("  <json>         Name of a configuration file in JSON format.                   ")
        print("  <csv>          Name of a configuration file in table format.                  ")
        print("                 (See example files in the '/preset' directory)                 ")
        print("                                                                                ")
        print("Option:                                                                         ")
        print("  For hosts with more than one IP or PORT, the option allows setting only       ")
        print("  the LiDARs connected to the specific IP and PORT.                             ")
        print("  It means if the option is not used, the default data receiving PORT (7256)    ")
        print("  on all IP addresses (INADDR_ANY) will be used in the command.                 ")
        print("  -I, --sender_ip <ip1> <ip2> ...    Sets the sender's IP.                      ")
        print("                                     So, the command will be sent to LiDARs who ")
        print("                                     has the condition:                         ")
        print("                                       data_dest_ip == <ip1> or <ip2> or  ...   ")
        print("  -P, --sender_port <pt1> <pt2> ...  Sets the sender's port.                    ")
        print("                                     Which means:                               ")
        print("                                       data_dest_port == <pt1> or <pt2> or ...  ")
        print("  -S, --sender <ip1>:<pt1> ...       Sets the both IP and port of the sender.   ")
        print("                                       data_dest_ip == <ip1> && port == <pt1> or")
        print("                                       data_dest_ip == <ip2> && port == <pt2> or")
        print("                                       ...                                      ")
        print(" * Note: The options -I and -P can be used together. In this case, the command  ")
        print("         will be excuted for all possible combinations of each options          ")
        print("                                                                                ")
        print("Example:                                                                        ")
        print("  1. Read infomation from all connected LiDARs:                                 ")
        print("    $ python ilidar-tool.py -i a                                                ")
        print("                                                                                ")
        print("  2. Set pause mode to LiDARs has 192.168.5.200 or 192.168.5.201:               ")
        print("    $ python ilidar-tool.py -p 192.168.5.200 192.168.5.201                      ")
        print("                                                                                ")
        print("  3. Set measurement mode to LiDARs has serial number 456 or 457:               ")
        print("    $ python ilidar-tool.py -m 456 457                                          ")
        print("                                                                                ")
        print("  4. Lock LiDARs has serial number 458 or 459 and data_dest_ip == 192.168.5.2:  ")
        print("    $ python ilidar-tool.py -l 458 459 -I 192.168.5.2                           ")
        print("                                                                                ")
        print("  5. Unlock LiDARs has serial number 460 or 461 and data_dest_port == 17256:    ")
        print("    $ python ilidar-tool.py -u 460 461 -P 17256                                 ")
        print("                                                                                ")
        print("  6. Update all LiDARs connected with specific IPs [192.168.5.2, 192.168.6.2]   ")
        print("    $ python ilidar-tool.py --update all -I 192.168.5.2 192.168.6.2             ")
        print("                                                                                ")
        print("  7. Update all LiDARs connected with specific ports list [7256, 7257, 7258]    ")
        print("    $ python ilidar-tool.py --update all -P 7256 7257 7258                      ")
        print("                                                                                ")
        print("  8. Convert the file input.csv to json format:                                 ")
        print("    $ python ilidar-tool.py --convert input.csv output.json                     ")
        print("                                                                                ")
        print("  9. Configure the LiDAR who has the same serial number in the file lidar0.json:")
        print("    $ python ilidar-tool.py --config lidar0.json                                ")
        print("                                                                                ")
        print("  10. Configure all the LiDARs from the files in /preset01 directory:           ")
        print("    $ python ilidar-tool.py --config /preset01                                  ")
        print("                                                                                ")
 
        parser.exit()

# Print function of info_v2 packet for F/W V1.5.0+
def print_info_v2(src):
    print(f"\t\tsensor_sn: {src['sensor_sn']}")
    print(f"\t\tcapture_mode: {src['capture_mode']}")
    print(f"\t\tcapture_row: {src['capture_row']}")
    print(f"\t\tcapture_shutter: {src['capture_shutter']}")
    print(f"\t\tcapture_limit: {src['capture_limit']}")
    print(f"\t\tcapture_period_us: {src['capture_period_us']}")
    print(f"\t\tcapture_seq: {src['capture_seq']}")
    print(f"\t\tdata_output: {src['data_output']}")
    print(f"\t\tdata_baud: {src['data_baud']}")
    data_sensor_ip = src['data_sensor_ip']
    print(f"\t\tdata_sensor_ip: {data_sensor_ip[0]}.{data_sensor_ip[1]}.{data_sensor_ip[2]}.{data_sensor_ip[3]}")
    data_dest_ip = src['data_dest_ip']
    print(f"\t\tdata_dest_ip: {data_dest_ip[0]}.{data_dest_ip[1]}.{data_dest_ip[2]}.{data_dest_ip[3]}")
    data_subnet = src['data_subnet']
    print(f"\t\tdata_subnet: {data_subnet[0]}.{data_subnet[1]}.{data_subnet[2]}.{data_subnet[3]}")
    data_gateway = src['data_gateway']
    print(f"\t\tdata_gateway: {data_gateway[0]}.{data_gateway[1]}.{data_gateway[2]}.{data_gateway[3]}")
    print(f"\t\tdata_port: {src['data_port']}")
    data_mac_addr = src['data_mac_addr']
    print(f"\t\tdata_mac_addr: {data_mac_addr[0]}:{data_mac_addr[1]}:{data_mac_addr[2]}_{data_mac_addr[3]}:{data_mac_addr[4]}:{data_mac_addr[5]}")
    print(f"\t\tsync: {src['sync']}")
    print(f"\t\tsync_trig_delay_us: {src['sync_trig_delay_us']}")
    print(f"\t\tsync_ill_delay_us: {src['sync_ill_delay_us']}")
    print(f"\t\tsync_trig_trim_us: {src['sync_trig_trim_us']}")
    print(f"\t\tsync_ill_trim_us: {src['sync_ill_trim_us']}")
    print(f"\t\tsync_output_delay_us: {src['sync_output_delay_us']}")
    print(f"\t\tarb: {src['arb']}")
    print(f"\t\tarb_timeout: {src['arb_timeout']}")

# Print function of changed parameters for for F/W V1.4.0+
def print_diff_info_v2(pri, post):
    diff = 0

    if pri['capture_mode'] != post['capture_mode']:
        diff += 1
        print(f"\t\tcapture_mode: {pri['capture_mode']}")
        print(f"\t\t          --> {post['capture_mode']}")
        
    if pri['capture_row'] != post['capture_row']:
        diff += 1
        print(f"\t\tcapture_row: {pri['capture_row']}")
        print(f"\t\t         --> {post['capture_row']}")
        
    if pri['capture_shutter'] != post['capture_shutter']:
        diff += 1
        print(f"\t\tcapture_shutter: {pri['capture_shutter']}")
        print(f"\t\t             --> {post['capture_shutter']}")
        
    if pri['capture_limit'] != post['capture_limit']:
        diff += 1
        print(f"\t\tcapture_limit: {pri['capture_limit']}")
        print(f"\t\t           --> {post['capture_limit']}")
        
    if pri['capture_period_us'] != post['capture_period_us']:
        diff += 1
        print(f"\t\tcapture_period_us: {pri['capture_period_us']}")
        print(f"\t\t               --> {post['capture_period_us']}")
        
    if pri['capture_seq'] != post['capture_seq']:
        diff += 1
        print(f"\t\tcapture_seq: {pri['capture_seq']}")
        print(f"\t\t         --> {post['capture_seq']}")
        
    if pri['data_output'] != post['data_output']:
        diff += 1
        print(f"\t\tdata_output: {pri['data_output']}")
        print(f"\t\t         --> {post['data_output']}")
        
    if pri['data_baud'] != post['data_baud']:
        diff += 1
        print(f"\t\tdata_baud: {pri['data_baud']}")
        print(f"\t\t       --> {post['data_baud']}")
        
    if pri['data_sensor_ip'] != bytearray(post['data_sensor_ip']):
        diff += 1
        arr = pri['data_sensor_ip']
        print(f"\t\tdata_sensor_ip: {arr[0]}.{arr[1]}.{arr[2]}.{arr[3]}")
        arr = post['data_sensor_ip']
        print(f"\t\t            --> {arr[0]}.{arr[1]}.{arr[2]}.{arr[3]}")
        
    if pri['data_dest_ip'] != bytearray(post['data_dest_ip']):
        diff += 1
        arr = pri['data_dest_ip']
        print(f"\t\tdata_dest_ip: {arr[0]}.{arr[1]}.{arr[2]}.{arr[3]}")
        arr = post['data_dest_ip']
        print(f"\t\t          --> {arr[0]}.{arr[1]}.{arr[2]}.{arr[3]}")
        
    if pri['data_subnet'] != bytearray(post['data_subnet']):
        diff += 1
        arr = pri['data_subnet']
        print(f"\t\tdata_subnet: {arr[0]}.{arr[1]}.{arr[2]}.{arr[3]}")
        arr = post['data_subnet']
        print(f"\t\t         --> {arr[0]}.{arr[1]}.{arr[2]}.{arr[3]}")
        
    if pri['data_gateway'] != bytearray(post['data_gateway']):
        diff += 1
        arr = pri['data_gateway']
        print(f"\t\tdata_gateway: {arr[0]}.{arr[1]}.{arr[2]}.{arr[3]}")
        arr = post['data_gateway']
        print(f"\t\t          --> {arr[0]}.{arr[1]}.{arr[2]}.{arr[3]}")
        
    if pri['data_port'] != post['data_port']:
        diff += 1
        print(f"\t\tdata_port: {pri['data_port']}")
        print(f"\t\t       --> {post['data_port']}")
        
    if pri['data_mac_addr'] != bytearray(post['data_mac_addr']):
        diff += 1
        arr = pri['data_mac_addr']
        print(f"\t\tdata_mac_addr: {arr[0]}:{arr[1]}:{arr[2]}_{arr[3]}:{arr[4]}:{arr[5]}")
        arr = post['data_mac_addr']
        print(f"\t\t           --> {arr[0]}:{arr[1]}:{arr[2]}_{arr[3]}:{arr[4]}:{arr[5]}")
        
    if pri['sync'] != post['sync']:
        diff += 1
        print(f"\t\tsync: {pri['sync']}")
        print(f"\t\t  --> {post['sync']}")
        
    if pri['sync_trig_delay_us'] != post['sync_trig_delay_us']:
        diff += 1
        print(f"\t\tsync_trig_delay_us: {pri['sync_trig_delay_us']}")
        print(f"\t\t                --> {post['sync_trig_delay_us']}")
        
    if pri['sync_ill_delay_us'] != post['sync_ill_delay_us']:
        diff += 1
        print(f"\t\tsync_ill_delay_us: {pri['sync_ill_delay_us']}")
        print(f"\t\t               --> {post['sync_ill_delay_us']}")
        
    if pri['sync_trig_trim_us'] != post['sync_trig_trim_us']:
        diff += 1
        print(f"\t\tsync_trig_trim_us: {pri['sync_trig_trim_us']}")
        print(f"\t\t               --> {post['sync_trig_trim_us']}")
        
    if pri['sync_ill_trim_us'] != post['sync_ill_trim_us']:
        diff += 1
        print(f"\t\tsync_ill_trim_us: {pri['sync_ill_trim_us']}")
        print(f"\t\t              --> {post['sync_ill_trim_us']}")
        
    if pri['sync_output_delay_us'] != post['sync_output_delay_us']:
        diff += 1
        print(f"\t\tsync_output_delay_us: {pri['sync_output_delay_us']}")
        print(f"\t\t                  --> {post['sync_output_delay_us']}")
        
    if pri['arb'] != post['arb']:
        diff += 1
        print(f"\t\tarb: {pri['arb']}")
        print(f"\t\t --> {post['arb']}")
        
    if pri['arb_timeout'] != post['arb_timeout']:
        diff += 1
        print(f"\t\tarb_timeout: {pri['arb_timeout']}")
        print(f"\t\t         --> {post['arb_timeout']}")

    return diff

# Get a list of JSON files in the current directory
def get_json_files(directory):
    json_files = [f for f in os.listdir(directory) if f.endswith('.json')]
    return json_files

# Check if the JSON file contains the required ilidar_version and parameters for V1.5.X
def validate_v1_5_x(data):
    required_fields = [
        "sensor_sn",
        "capture_mode",
        "capture_row",
        "capture_shutter",
        "capture_limit",
        "capture_period_us",
        "capture_seq",
        "data_output",
        "data_baud",
        "data_sensor_ip",
        "data_dest_ip",
        "data_subnet",
        "data_gateway",
        "data_port",
        "data_mac_addr",
        "sync",
        "sync_trig_delay_us",
        "sync_ill_delay_us",
        "sync_trig_trim_us",
        "sync_ill_trim_us",
        "sync_output_delay_us",
        "arb",
        "arb_timeout"
    ]
    
    # Check if all required fields are in the data
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        return False
    else:
        return True

# Check the ilidar_version and process accordingly
def check_ilidar_param_version(data):
    ilidar_version = data.get('ilidar_version')

    if ilidar_version and ilidar_version.startswith('1.5'):
        # Handle for versions in the V1.5.X range
        return validate_v1_5_x(data)
    else:
        # Skip other versions
        return False

# Read the data from each JSON file
def read_json_files(json_files):
    json_file_and_data = []

    # List all files in the directory
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as file:
                # Load the file
                data = json.load(file)

                # Check dict or list
                if isinstance(data, dict):
                    # Check parameter file version
                    if check_ilidar_param_version(data):
                        # Add the JSON data to the list
                        json_file_and_data.append((json_file, data))
                elif isinstance(data, list):
                    for d in data:
                        # Check parameter file version
                        if check_ilidar_param_version(d):
                            # Add the JSON data to the list
                            json_file_and_data.append((json_file, d))

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from file {json_file}: {e}")

        except Exception as e:
            print(f"An error occurred while reading file {json_file}: {e}")
    
    return json_file_and_data

#### COMMAND BODY FUNCTIONS ####
def cmd_run(cmd_msg, net_msg):
    # Get message
    command = cmd_msg['command']
    target_type = cmd_msg['target_type']
    target_list = cmd_msg['target_list']

    host_list = net_msg['listening_list']
    sensor_config_port = 4906

    # Command definitions
    cmd_read_info       = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x00, 0x03, 0x00, 0x00, 0xA5, 0x5A])
    cmd_measure         = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x00, 0x01, 0x00, 0x00, 0xA5, 0x5A])
    cmd_pause           = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x01, 0x01, 0x00, 0x00, 0xA5, 0x5A])
    cmd_reboot          = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x02, 0x01, 0x00, 0x00, 0xA5, 0x5A])
    cmd_reset_factory   = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x00, 0x02, 0x00, 0x00, 0xA5, 0x5A])
    cmd_redirect        = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x00, 0x04, 0x00, 0x00, 0xA5, 0x5A])
    cmd_lock            = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x00, 0x05, 0x00, 0x00, 0xA5, 0x5A])
    cmd_unlock          = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x01, 0x05, 0x00, 0x00, 0xA5, 0x5A])

    # Packet headers
    status_header       = bytearray([0xA5, 0x5A, 0x10, 0x00, 0x1C, 0x00])
    status_full_header  = bytearray([0xA5, 0x5A, 0x11, 0x00, 0x38, 0x01])
    info_v2_header      = bytearray([0xA5, 0x5A, 0x21, 0x00, 0xA6, 0x00])
    ack_header          = bytearray([0xA5, 0x5A, 0x40, 0x00, 0x22, 0x00])
    flash_block_headder = bytearray([0xA5, 0x5A, 0x00, 0x01, 0x26, 0x04])
    tail                = bytearray([0xA5, 0x5A])

    # Check target
    if 'ALL' in target_type:
        target_list = []
        recv_sn_list = []
        recv_info_list = []
    else:
        recv_sn_list = [0] * len(target_list)
        recv_info_list = []

    if command == 'info':
        cmd_packet = cmd_read_info
    if command == 'pause':
        cmd_packet = cmd_pause
    elif command == 'measure':
        cmd_packet = cmd_measure
    elif command == 'lock':
        cmd_packet = cmd_lock
    elif command == 'unlock':
        cmd_packet = cmd_unlock
    elif command == 'reboot':
        cmd_packet = cmd_reboot
    elif command == 'redirect':
        cmd_packet = cmd_redirect
    elif command == 'reset':
        cmd_packet = cmd_reset_factory
    
    # Print
    print('')
    
    # Create sockets
    sockets = {}
    for ip, item in host_list.items():
        for port in item['port']:
            sockData = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sockData.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sockData.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 16 * 1024 * 1024)
            sockData.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16 * 1024 * 1024)
            sockData.bind((ip, port))
            sockData.setblocking(0)

            if ip in sockets:
                sockets[ip]['data'].append(sockData)
            else:
                sockets[ip] = { 'data': [sockData] }

            sockets[ip][port] = sockData

        sockConfig = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sockConfig.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sockConfig.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sockConfig.bind((ip, 7257))
        sockets[ip]['config'] = sockConfig
        sockets[ip]['subnet'] = item['subnet']
        sockets[ip]['broadcast'] = item['config']

    # Start to find lidars
    print('Start to find LiDARs by sending cmd_read_info packet.. (You can exit this process with Enter key)')
    check_cnt = 0
    while True:
        if is_enter_pressed():
            print('  caught Enter-key!')
            print('Stop finding LiDARs.')
            break
        
        # Send cmd_read_info
        for ip, sock in sockets.items():
            sock['config'].sendto(cmd_read_info, (sock['broadcast'], sensor_config_port))
            
            # Try to read info
            for sock_read in sock['data']:
                while True:
                    try:
                        data, sender = sock_read.recvfrom(2000)
                    except OSError:
                        # There is no data in the socket buffer
                        break

                    if len(data) == (166 + 8) and data[:6] == info_v2_header:
                        # Info_v2 packet was received
                        info_v2 = decode_info_v2(data[6:172])
                        
                        if target_type[0] == 'ALL':
                            # Add the serial number to the target list
                            if info_v2['sensor_sn'] not in recv_sn_list:
                                recv_info_list.append((len(recv_sn_list), info_v2))
                                recv_sn_list.append(info_v2['sensor_sn'])
                                target_list.append(sender[0])
                                print('  LiDAR #' + '{:02}'.format(len(recv_sn_list) - 1) + ' was found!' +
                                      '  SN ' + str(info_v2['sensor_sn']) +
                                      '  [LiDAR] ' + sender[0] + ' ->  [DEST] ' + ip + ':' + str(info_v2['data_port']))
                        else:
                            if info_v2['sensor_sn'] in target_list:
                                for target_idx, target in enumerate(target_list):
                                    if info_v2['sensor_sn'] == target and recv_sn_list[target_idx] == 0:
                                        recv_sn_list[target_idx] = info_v2['sensor_sn']
                                        target_list[target_idx] = sender[0]
                                        target_type[target_idx] = 'IP'
                                        recv_info_list.append((target_idx, info_v2))
                                        print('  LiDAR #' + '{:02}'.format(target_idx) + ' was found!' +
                                              '  SN ' + str(info_v2['sensor_sn']) +
                                              '  [LiDAR] ' + sender[0] + ' ->  [DEST] ' + ip + ':' + str(info_v2['data_port']))
                            elif sender[0] in target_list:
                                for target_idx, target in enumerate(target_list):
                                    if sender[0] == target and recv_sn_list[target_idx] == 0:
                                        recv_sn_list[target_idx] = info_v2['sensor_sn']
                                        recv_info_list.append((target_idx, info_v2))
                                        print('  LiDAR #' + '{:02}'.format(target_idx) + ' was found!' +
                                              '  SN ' + str(info_v2['sensor_sn']) +
                                              '  [LiDAR] ' + sender[0] + ' ->  [DEST] ' + ip + ':' + str(info_v2['data_port']))

        # Wait for 10 ms
        time.sleep(0.01)
        
        # Check read status
        if target_type[0] != 'ALL' and 0 not in recv_sn_list:
            print('Success to find all LiDARs!')
            break

        check_cnt = check_cnt + 1
        if check_cnt > 50:
            check_cnt = 0
            if target_type[0] == 'ALL':
                print('  wait for other LiDARs... [ FOUND ' + str(len(recv_sn_list)) + ' ] (Enter-key to break)')
            else:
                print('  wait for other LiDARs... [ FOUND ' + str(len([sn for sn in recv_sn_list if sn != 0])) + ' / TARGET ' + str(len(recv_sn_list)) + ' ] (Enter-key to break)')

    # Check read result
    if any(recv_sn_list):
        print("Found LiDARs:")
        for recv_sn_idx, recv_sn in enumerate(recv_sn_list):
            if recv_sn != 0:
                print('  #' + '{:02}'.format(recv_sn_idx) + '  SN ' + str(recv_sn) + '  ' + target_list[recv_sn_idx])
    else:
        print('There are no found LiDARs. Please check the network setup...')
        # Close sockets
        for ip, item in sockets.items():
            for sock in item['data']:
                sock.close()
            item['config'].close()
        return
    
    print('')
    print('Done!')

    # Do command
    if command == 'info':
        # Print
        print('Success to read info: (sorted by sensor_sn)')

        # Create json file to save details
        read_dir = os.path.join(get_executable_path(), 'read')
        os.makedirs(read_dir, exist_ok=True)
       
        current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file_name = os.path.join(read_dir, f'info_{current_time}.json')
        
        delete_keys = {'sensor_hw_id', 'sensor_fw_ver', 'sensor_fw_date', 'sensor_fw_time',
                       'sensor_calib_id', 'sensor_fw0_ver', 'sensor_fw1_ver', 'sensor_fw2_ver',
                       'sensor_model_id', 'sensor_boot_ctrl', 'lock'}
        
        output_info = []

        # Sort
        sorted_recv_sn = sorted(recv_sn_list)

        # Store
        for sn in sorted_recv_sn:
            for idx, info in recv_info_list:
                if info['sensor_sn'] == sn:
                    recv_info = info

                    # Print
                    fw_ver = recv_info['sensor_fw_ver']
                    str_fw_ver = f'{fw_ver[2]}.{fw_ver[1]}.{fw_ver[0]}'
                    print('  SN ' + str(sn)
                        + '  F/W V' + str_fw_ver
                        + ' (' + recv_info['sensor_fw_date'].decode('utf-8') + ')')
                    
                    print('  MODE' + str(recv_info['capture_mode'])
                        + '   period ' + str(recv_info['capture_period_us']) + ' us'
                        + '  shutter ' + str(recv_info['capture_shutter']) + ' us')

                    # Convert info to config json data 
                    stored_data = {key: value for key, value in recv_info.items() if key not in delete_keys}
                    stored_data['data_sensor_ip'] = list(stored_data['data_sensor_ip'])
                    stored_data['data_dest_ip'] = list(stored_data['data_dest_ip'])
                    stored_data['data_subnet'] = list(stored_data['data_subnet'])
                    stored_data['data_gateway'] = list(stored_data['data_gateway'])
                    stored_data['data_mac_addr'] = list(stored_data['data_mac_addr'])

                    # Append it to output
                    output_info.append(stored_data)

        with open(output_file_name, 'w', encoding='utf-8') as output_file:
            json.dump(output_info, output_file, indent=4)

        print('See details on output json file' + f' info_{current_time}.json' + ' in the /read directory.')
    else:
        # Print
        print('Start to send command: cmd_' + command)

        for recv_sn_idx, recv_sn in enumerate(recv_sn_list):
            if recv_sn != 0:
                # Send command
                cmd_packet[8:10] = bytearray([recv_sn%256, recv_sn//256])

                for ip, sock in sockets.items():
                    if is_in_subnet(target_list[recv_sn_idx], ip, sock['subnet']):
                        sock['config'].sendto(cmd_packet, (target_list[recv_sn_idx], sensor_config_port))

                        # Print
                        print('  #' + '{:02}'.format(recv_sn_idx) + '  [HOST] ' + ip + ':' + str(7257)
                            + ' -> [LiDAR] ' + target_list[recv_sn_idx] + ':' + str(sensor_config_port))
            else:
                print('  #' + '{:02}'.format(recv_sn_idx) + '  (skipped)')

        # Print
        print('Success to send cmd_' + command + ' packet!')

    # Close sockets
    for ip, item in sockets.items():
        for sock in item['data']:
            sock.close()
        item['config'].close()
    return

def cmd_sendonly(cmd_msg, net_msg):
    # Get message
    command = cmd_msg['command']
    target_type = cmd_msg['target_type']
    target_list = cmd_msg['target_list']

    host_list = net_msg['listening_list']
    sensor_config_port = 4906

    # Command definitions
    cmd_measure         = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x00, 0x01, 0x00, 0x00, 0xA5, 0x5A])
    cmd_pause           = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x01, 0x01, 0x00, 0x00, 0xA5, 0x5A])
    cmd_reboot          = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x02, 0x01, 0x00, 0x00, 0xA5, 0x5A])
    cmd_redirect        = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x00, 0x04, 0x00, 0x00, 0xA5, 0x5A])

    # Packet headers
    status_header       = bytearray([0xA5, 0x5A, 0x10, 0x00, 0x1C, 0x00])
    status_full_header  = bytearray([0xA5, 0x5A, 0x11, 0x00, 0x38, 0x01])
    info_v2_header      = bytearray([0xA5, 0x5A, 0x21, 0x00, 0xA6, 0x00])
    ack_header          = bytearray([0xA5, 0x5A, 0x40, 0x00, 0x22, 0x00])
    flash_block_headder = bytearray([0xA5, 0x5A, 0x00, 0x01, 0x26, 0x04])
    tail                = bytearray([0xA5, 0x5A])
    
    # Get command packet
    if command == 'pause':
        cmd_packet = cmd_pause
    elif command == 'measure':
        cmd_packet = cmd_measure
    elif command == 'reboot':
        cmd_packet = cmd_reboot
    elif command == 'redirect':
        cmd_packet = cmd_redirect
    else:
        cmd_run(cmd_msg, net_msg)
        return
    
    # Print
    print('')
    print('All arguments are IP addresses. So, the command packet will simply be sent to the LiDARs.')
    
   # Create sockets
    sockets = {}
    for ip, item in host_list.items():
        for port in item['port']:
            sockData = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sockData.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sockData.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 16 * 1024 * 1024)
            sockData.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16 * 1024 * 1024)
            sockData.bind((ip, port))
            sockData.setblocking(0)

            if ip in sockets:
                sockets[ip]['data'].append(sockData)
            else:
                sockets[ip] = { 'data': [sockData] }

            sockets[ip][port] = sockData

        sockConfig = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sockConfig.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sockConfig.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sockConfig.bind((ip, 7257))
        sockets[ip]['config'] = sockConfig
        sockets[ip]['subnet'] = item['subnet']
        sockets[ip]['broadcast'] = item['config']

    # Send command
    print('Start to send cmd_' + command + ' packet to the LiDARs..')

    # Check target
    target_idx = 0
    if 'ALL' in target_type:
        for ip, sock in sockets.items():
            sock['config'].sendto(cmd_packet, (sock['broadcast'], sensor_config_port))
            print('  #' + '{:02}'.format(target_idx) + '  [HOST] ' + ip + ':' + str(7257) + ' -> [LiDAR] ' + sock['broadcast'] + ':' + str(sensor_config_port))
            target_idx = target_idx + 1

    else:
        for target in target_list:
            for ip, sock in sockets.items():
                if is_in_subnet(target, ip, sock['subnet']):
                    sock['config'].sendto(cmd_packet, (sock['broadcast'], sensor_config_port))
                    print('  #' + '{:02}'.format(target_idx) + '  [HOST] ' + ip + ':' + str(7257) + ' -> [LiDAR] ' + sock['broadcast'] + ':' + str(sensor_config_port))
                    target_idx = target_idx + 1

    print('Success to send cmd_' + command + ' packet!')

    # Close sockets
    for ip, item in sockets.items():
        for sock in item['data']:
            sock.close()
        item['config'].close()
    return

def cmd_config_run(file_msg, net_msg):
    # Print
    print('')
    print('Start to find the configuration files:')

    # Get message
    file_list = file_msg['file_list']

    host_list = net_msg['listening_list']
    sensor_config_port = 4906

    # Command definitions
    cmd_read_info       = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x00, 0x03, 0x00, 0x00, 0xA5, 0x5A])
    cmd_reboot          = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x02, 0x01, 0x00, 0x00, 0xA5, 0x5A])
    cmd_store           = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x03, 0x01, 0x00, 0x00, 0xA5, 0x5A])

    # Packet headers
    status_header       = bytearray([0xA5, 0x5A, 0x10, 0x00, 0x1C, 0x00])
    status_full_header  = bytearray([0xA5, 0x5A, 0x11, 0x00, 0x38, 0x01])
    info_v2_header      = bytearray([0xA5, 0x5A, 0x21, 0x00, 0xA6, 0x00])
    ack_header          = bytearray([0xA5, 0x5A, 0x40, 0x00, 0x22, 0x00])
    flash_block_headder = bytearray([0xA5, 0x5A, 0x00, 0x01, 0x26, 0x04])
    tail                = bytearray([0xA5, 0x5A])
    
    # Read and check each JSON file
    param_list = read_json_files(file_list)

    # Print read files
    for param_index, item in enumerate(param_list):
        # Add the parameters that you want to see here
        data_sensor_ip = item[1]['data_sensor_ip']
        print('  #' + '{:02}'.format(param_index), end='', flush=True)
        if data_sensor_ip == '':
            print(f"  SN {item[1]['sensor_sn']}  Unknown  ...")
        else:
            print(f"  SN {item[1]['sensor_sn']}  {data_sensor_ip[0]}.{data_sensor_ip[1]}.{data_sensor_ip[2]}.{data_sensor_ip[3]}  ...")

    # Check duplicates
    target_list = [item[1]['sensor_sn'] for item in param_list]
    duplicates = list(set([item for item in target_list if target_list.count(item) > 1]))
    if len(duplicates) > 0:
        print('  SN ' + str(duplicates) + ' are duplicated!')
        print('  invalid file formats.')
        return
    
    print('Success to find ' + str(len(target_list)) + ' configuration files!')

    # Initialize
    recv_sn_list = [0] * len(target_list)
    recv_info_list = []
    
    # Create sockets
    sockets = {}
    for ip, item in host_list.items():
        for port in item['port']:
            sockData = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sockData.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sockData.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 16 * 1024 * 1024)
            sockData.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16 * 1024 * 1024)
            sockData.bind((ip, port))
            sockData.setblocking(0)

            if ip in sockets:
                sockets[ip]['data'].append(sockData)
            else:
                sockets[ip] = { 'data': [sockData] }
                
            sockets[ip][port] = sockData

        sockConfig = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sockConfig.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sockConfig.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sockConfig.bind((ip, 7257))
        sockets[ip]['config'] = sockConfig
        sockets[ip]['subnet'] = item['subnet']
        sockets[ip]['broadcast'] = item['config']

    # Start to find lidars
    print('Start to find LiDARs by sending cmd_read_info packet.. (You can exit this process with Enter key)')
    check_cnt = 0
    while True:
        if is_enter_pressed():
            print('  caught Enter-key!')
            print('Stop finding LiDARs.')
            break
        
        # Send cmd_read_info
        for ip, sock in sockets.items():
            sock['config'].sendto(cmd_read_info, (sock['broadcast'], sensor_config_port))
            
            # Try to read info
            for sock_read in sock['data']:
                while True:
                    try:
                        data, sender = sock_read.recvfrom(2000)
                    except OSError:
                        # There is no data in the socket buffer
                        break

                    if len(data) == (166 + 8) and data[:6] == info_v2_header:
                        # Info_v2 packet was received
                        info_v2 = decode_info_v2(data[6:172])
                        
                        if info_v2['sensor_sn'] in target_list:
                            for target_idx, target in enumerate(target_list):
                                if info_v2['sensor_sn'] == target and recv_sn_list[target_idx] == 0:
                                    recv_sn_list[target_idx] = info_v2['sensor_sn']
                                    target_list[target_idx] = sender[0]
                                    recv_info_list.append((target_idx, info_v2))
                                    print('  LiDAR #' + '{:02}'.format(target_idx) + ' was found!' +
                                          '  SN ' + str(info_v2['sensor_sn']) +
                                          '  [LiDAR] ' + sender[0] + ' -> [DEST] ' + ip + ':' + str(info_v2['data_port']))

        # Wait for 10 ms
        time.sleep(0.01)
        
        # Check read status
        if 0 not in recv_sn_list:
            print('Success to find all LiDARs!')
            break

        check_cnt = check_cnt + 1
        if check_cnt > 50:
            check_cnt = 0
            print('  wait for other LiDARs... [ FOUND ' + str(len([sn for sn in recv_sn_list if sn != 0])) + ' / TARGET ' + str(len(recv_sn_list)) + ' ] (Enter-key to break)')

    # Check read result
    if any(recv_sn_list):
        print("Found LiDARs:")
        for recv_sn_idx, recv_sn in enumerate(recv_sn_list):
            if recv_sn != 0:
                print('  #' + '{:02}'.format(recv_sn_idx) + '  SN ' + str(recv_sn) + '  ' + target_list[recv_sn_idx])
    else:
        print('There are no found LiDARs. Please check the network setup...')
        # Close sockets
        for ip, item in sockets.items():
            for sock in item['data']:
                sock.close()
            item['config'].close()
        return
    
    print("Start to config LiDARs:")
    config_cnt = 0
    for param_idx, param in enumerate(param_list):
        if recv_sn_list[param_idx] != 0:
            print(f"  SN {recv_sn_list[param_idx]}")
            for item in recv_info_list:
                if item[0] == param_idx:
                    if item[1]['lock'] != 0:
                        print('    this LiDAR is locked! (skipped)')
                    else:
                        unchanged_params = overwrite_info_v2(item[1], param[1])
                        if len(unchanged_params) > 0:
                            print('    empty ' + str(len(unchanged_params)) + ' parameters will be maintained as values stored in the sensor.')

                        if print_diff_info_v2(item[1], param[1]) > 0:
                            config_info_v2 = info_v2_header + encode_info_v2(param[1]) + tail

                            for ip, sock in sockets.items():
                                if is_in_subnet(target_list[param_idx], ip, sock['subnet']):
                                    print("    send config packet to the LiDAR.")
                                    sock['config'].sendto(config_info_v2, (target_list[param_idx], sensor_config_port))
                                    time.sleep(1)

                                    print("    send cmd_store to the LiDAR.")
                                    sock['config'].sendto(cmd_store, (target_list[param_idx], sensor_config_port))
                                    time.sleep(1)

                            config_cnt = config_cnt + 1
                        else:
                            print("    nothing to be changed. (skipped)")
    
    if config_cnt == 0:
        print('Done!')
        # Close sockets
        for ip, item in sockets.items():
            for sock in item['data']:
                sock.close()
            item['config'].close()
        return

    print('Wait for cmd_store', end='', flush=True)
    for i in range(5):
        time.sleep(1)
        print('.', end='', flush=True)
    print('')
    print('Success to configure LiDARs!')

    print('Reboot the LiDARs:')
    for param_idx, param in enumerate(param_list):
        if recv_sn_list[param_idx] != 0:
            print(f"  SN {recv_sn_list[param_idx]}")
            for ip, sock in sockets.items():
                if is_in_subnet(target_list[param_idx], ip, sock['subnet']):
                    sock['config'].sendto(cmd_reboot, (target_list[param_idx], sensor_config_port))
            
    print('Wait for cmd_reboot', end='', flush=True)
    for i in range(5):
        time.sleep(1)
        print('.', end='', flush=True)

    print('Done!')
    print('')

    # Close sockets
    for ip, item in sockets.items():
        for sock in item['data']:
            sock.close()
        item['config'].close()
    
    return

def cmd_convert_run(file_msg):
    file_list = file_msg['file_list']

    csv_file_name = file_list[0]
    output_file_name = file_list[1]

    store_data = []

    print('')
    print('Start to convert the file:')

    # Read and print CSV content
    with open(csv_file_name, mode='r') as file:
        reader = csv.reader(file)
        
        # Print the first few rows of the CSV
        for i, row in enumerate(reader):
            if row[1].startswith('1.4'):
                print("  F/W 1.4.X is not supported..")
            elif row[1].startswith('1.5'):
                if len(row) == 44:
                    data = {}
                    data['ilidar_name']             = row[0]
                    data['ilidar_version']          = row[1]
                    data['sensor_sn']               = int(row[2])
                    data['capture_mode']            = int(row[3]) if row[3] != '' else ''
                    data['capture_row']             = int(row[4]) if row[4] != '' else ''
                    data['capture_shutter']         = [''] * 5
                    data['capture_shutter'][0]      = int(row[5]) if row[5] != '' else ''
                    data['capture_shutter'][1]      = int(row[6]) if row[6] != '' else ''
                    data['capture_shutter'][2]      = int(row[7]) if row[7] != '' else ''
                    data['capture_shutter'][3]      = int(row[8]) if row[8] != '' else ''
                    data['capture_shutter'][4]      = int(row[9]) if row[9] != '' else ''
                    data['capture_limit']           = [''] * 2
                    data['capture_limit'][0]        = int(row[10]) if row[10] != '' else ''
                    data['capture_limit'][1]        = int(row[11]) if row[11] != '' else ''
                    data['capture_period_us']       = int(row[12]) if row[12] != '' else ''
                    data['capture_seq']             = int(row[13]) if row[13] != '' else ''
                    data['data_output']             = int(row[14]) if row[14] != '' else ''
                    data['data_baud']               = int(row[15]) if row[15] != '' else ''
                    data['data_sensor_ip']          = [int(data_sensor_ip) for data_sensor_ip in row[16].split('.')] if row[16] != '' else ''
                    data['data_dest_ip']            = [int(data_dest_ip) for data_dest_ip in row[17].split('.')] if row[17] != '' else ''
                    data['data_subnet']             = [int(data_subnet) for data_subnet in row[18].split('.')] if row[18] != '' else ''
                    data['data_gateway']            = [int(data_gateway) for data_gateway in row[19].split('.')] if row[19] != '' else ''
                    data['data_port']               = int(row[20]) if row[20] != '' else ''
                    data['data_mac_addr']           = [int(data_mac_addr) for data_mac_addr in row[21].replace('_', ':').split(':')] if row[21] != '' else ''
                    data['sync']                    = int(row[22]) if row[22] != '' else ''
                    data['sync_trig_delay_us']      = int(row[23]) if row[23] != '' else ''
                    data['sync_ill_delay_us']       = [''] * 15
                    data['sync_ill_delay_us'][0]    = int(row[24]) if row[24] != '' else ''
                    data['sync_ill_delay_us'][1]    = int(row[25]) if row[25] != '' else ''
                    data['sync_ill_delay_us'][2]    = int(row[26]) if row[26] != '' else ''
                    data['sync_ill_delay_us'][3]    = int(row[27]) if row[27] != '' else ''
                    data['sync_ill_delay_us'][4]    = int(row[28]) if row[28] != '' else ''
                    data['sync_ill_delay_us'][5]    = int(row[29]) if row[29] != '' else ''
                    data['sync_ill_delay_us'][6]    = int(row[30]) if row[30] != '' else ''
                    data['sync_ill_delay_us'][7]    = int(row[31]) if row[31] != '' else ''
                    data['sync_ill_delay_us'][8]    = int(row[32]) if row[32] != '' else ''
                    data['sync_ill_delay_us'][9]    = int(row[33]) if row[33] != '' else ''
                    data['sync_ill_delay_us'][10]   = int(row[34]) if row[34] != '' else ''
                    data['sync_ill_delay_us'][11]   = int(row[35]) if row[35] != '' else ''
                    data['sync_ill_delay_us'][12]   = int(row[36]) if row[36] != '' else ''
                    data['sync_ill_delay_us'][13]   = int(row[37]) if row[37] != '' else ''
                    data['sync_ill_delay_us'][14]   = int(row[38]) if row[38] != '' else ''
                    data['sync_trig_trim_us']       = int(row[39]) if row[39] != '' else ''
                    data['sync_ill_trim_us']        = int(row[40]) if row[40] != '' else ''
                    data['sync_output_delay_us']    = int(row[41]) if row[41] != '' else ''
                    data['arb']                     = int(row[42]) if row[42] != '' else ''
                    data['arb_timeout']             = int(row[43]) if row[43] != '' else ''

                    store_data.append(data)

                    print('  SN ' + str(data['sensor_sn']) + ' was append.')
                else:
                    print('  not enough elements for F/W 1.5.X. (skipped)')
            else:
                print("  target F/W version must be 1.5.X")

    with open(output_file_name, mode='w', encoding='utf-8') as jsonf:
        json.dump(store_data, jsonf, indent=4)

    print('Success to convert the file!')
    return

def cmd_update_run(forced_update, cmd_msg, net_msg):
    print('')
    print('Start to read the firmware files:')

    # Get message
    command = cmd_msg['command']
    target_type = cmd_msg['target_type']
    arg_target_list = cmd_msg['target_list']

    host_list = net_msg['listening_list']
    sensor_config_port = 4906

    # Command definitions
    cmd_read_info       = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x00, 0x03, 0x00, 0x00, 0xA5, 0x5A])
    cmd_measure         = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x00, 0x01, 0x00, 0x00, 0xA5, 0x5A])
    cmd_pause           = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x01, 0x01, 0x00, 0x00, 0xA5, 0x5A])
    cmd_reboot          = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x02, 0x01, 0x00, 0x00, 0xA5, 0x5A])
    cmd_safe_boot       = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x04, 0x01, 0x00, 0x00, 0xA5, 0x5A])

    cmd_unlock          = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x01, 0x05, 0x00, 0x00, 0xA5, 0x5A])

    cmd_flash_start     = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0x00, 0x06, 0x00, 0x00, 0xA5, 0x5A])
    cmd_flash_finish    = bytearray([0xA5, 0x5A, 0x30, 0x00, 0x04, 0x00, 0xFF, 0x06, 0x00, 0x00, 0xA5, 0x5A])

    # Packet headers
    status_header       = bytearray([0xA5, 0x5A, 0x10, 0x00, 0x1C, 0x00])
    status_full_header  = bytearray([0xA5, 0x5A, 0x11, 0x00, 0x38, 0x01])
    info_v2_header      = bytearray([0xA5, 0x5A, 0x21, 0x00, 0xA6, 0x00])
    ack_header          = bytearray([0xA5, 0x5A, 0x40, 0x00, 0x22, 0x00])
    flash_block_headder = bytearray([0xA5, 0x5A, 0x00, 0x01, 0x26, 0x04])
    tail                = bytearray([0xA5, 0x5A])

    # Get the list of bin files
    bin_files = get_bin_files(os.getcwd() + '/bin')

    # Read the files
    if bin_files:
        # Read and check each JSON file
        bin_list = read_bin_files(bin_files)
        print(f"  found {len(bin_list)} firmware files:")
        time.sleep(1)

        # Print read files
        print("    SN ", end="", flush=True)
        for item in bin_list:
            # Add the parameters that you want to see here
            print(f"{item['sensor_sn']} ", end="", flush=True)
        print(" ")

    else:
        print("  no bin files found in the /bin directory.")
        return

    if len(bin_list) == 0:
        print("  no valid bin files found in the /bin directory.")
        return
    
    # Check duplicates
    target_list = [item['sensor_sn'] for item in bin_list]
    duplicates = list(set([item for item in target_list if target_list.count(item) > 1]))
    if len(duplicates) > 0:
        print('  SN ' + str(duplicates) + ' are duplicated!')
        print('  invalid files.')
        return
    
    print('Success to find ' + str(len(target_list)) + ' firmware files!')

    # Initialize
    recv_sn_list = [0] * len(bin_list)
    recv_info_list = []
    
    # Create sockets
    sockets = {}
    for ip, item in host_list.items():
        for port in item['port']:
            sockData = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sockData.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sockData.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 16 * 1024 * 1024)
            sockData.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16 * 1024 * 1024)
            sockData.bind((ip, port))
            sockData.setblocking(0)

            if ip in sockets:
                sockets[ip]['data'].append(sockData)
            else:
                sockets[ip] = { 'data': [sockData] }
                
            sockets[ip][port] = sockData

        sockConfig = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sockConfig.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sockConfig.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sockConfig.bind((ip, 7257))
        sockets[ip]['config'] = sockConfig
        sockets[ip]['subnet'] = item['subnet']
        sockets[ip]['broadcast'] = item['config']

    # Send cmd_measure to get LiDARs
    print('Resume all the connected LiDARs.')
    for ip, sock in sockets.items():
        sock['config'].sendto(cmd_measure, (sock['broadcast'], sensor_config_port))
    time.sleep(1)

    # Send cmd_safe_boot to all
    print('Reboot all the connected LiDARs with safe-boot mode. (This may take up to 10 sec...) ', end='', flush=True)
    for ip, sock in sockets.items():
        sock['config'].sendto(cmd_safe_boot, (sock['broadcast'], sensor_config_port))
    for i in range(5):
        time.sleep(1)
        print('.', end='', flush=True)
    print('')

    # Start to find lidars
    print('Start to find LiDARs by sending cmd_read_info packet.. (You can exit this process with Enter key)')
    check_cnt = 0
    while True:
        if is_enter_pressed():
            print('  caught Enter-key!')
            print('Stop finding LiDARs.')
            break
        
        # Send cmd_read_info
        for ip, sock in sockets.items():
            sock['config'].sendto(cmd_read_info, (sock['broadcast'], sensor_config_port))
            
            # Try to read info
            for sock_read in sock['data']:
                while True:
                    try:
                        data, sender = sock_read.recvfrom(2000)
                    except OSError:
                        # There is no data in the socket buffer
                        break

                    if len(data) == (166 + 8) and data[:6] == info_v2_header:
                        # Info_v2 packet was received
                        info_v2 = decode_info_v2(data[6:172])
                        
                        if info_v2['sensor_sn'] in target_list:
                            for target_idx, target in enumerate(target_list):
                                if info_v2['sensor_sn'] == target and recv_sn_list[target_idx] == 0:
                                    recv_sn_list[target_idx] = info_v2['sensor_sn']
                                    target_list[target_idx] = sender[0]
                                    recv_info_list.append((target_idx, info_v2))
                                    print('  LiDAR #' + '{:02}'.format(target_idx) + ' was found!' +
                                          '  SN ' + str(info_v2['sensor_sn']) +
                                          '  [LiDAR] ' + sender[0] + ' -> [DEST] ' + ip + ':' + str(info_v2['data_port']))
                                    
                    else:
                        for ip, sock in sockets.items():
                            if is_in_subnet(sender[0], ip, sock['subnet']):
                                sock['config'].sendto(cmd_pause, (sender[0], sensor_config_port))

        # Wait for 10 ms
        time.sleep(0.01)
        
        # Check read status
        if 0 not in recv_sn_list:
            print('Success to find all LiDARs!')
            break

        check_cnt = check_cnt + 1
        if check_cnt > 50:
            check_cnt = 0
            print('  wait for other LiDARs... [ FOUND ' + str(len([sn for sn in recv_sn_list if sn != 0])) + ' / FILE ' + str(len(recv_sn_list)) + ' ] (Enter-key to break)')

    # Check read result
    if any(recv_sn_list):
        print("Found LiDARs:")
        for recv_sn_idx, recv_sn in enumerate(recv_sn_list):
            if recv_sn != 0:
                print('  #' + '{:02}'.format(recv_sn_idx) + '  SN ' + str(recv_sn) + '  IP ' + target_list[recv_sn_idx])
    else:
        print('There are no found LiDARs. Please check the network setup...')
        # Close sockets
        for ip, item in sockets.items():
            for sock in item['data']:
                sock.close()
            item['config'].close()
        return

    print('Send cmd_pause to all LiDARs.')
    for ip, sock in sockets.items():
        sock['config'].sendto(cmd_pause, (sock['broadcast'], sensor_config_port))
    time.sleep(1)
    
    # Result variables
    sensor_updated = []
    sensor_skipped = []

    print("Start to update LiDARs:")
    for bin_idx, item in enumerate(bin_list):
        if recv_sn_list[bin_idx] != 0:
            print(f"  SN {item['sensor_sn']}")
            for info in recv_info_list:
                if info[1]['sensor_sn'] == item['sensor_sn']:
                    sensor_skipped.append(item['sensor_sn'])

                    target_ip = target_list[bin_idx]

                    if target_type[0] != 'ALL':
                        if target_ip not in arg_target_list and recv_sn_list[bin_idx] not in arg_target_list:
                            print('    this sensor is not in the argument list. (skipped)')
                            break

                    # Send cmd_pause to all
                    for ip, sock in sockets.items():
                        sock['config'].sendto(cmd_pause, (sock['broadcast'], sensor_config_port))

                    # Check the firmware version
                    if list(info[1]['sensor_fw1_ver']) == list(item['fw_version']):
                        print(f"    the sensor already has the firmware {item['fw_type']} V{item['fw_version'][2]}.{item['fw_version'][1]}.{item['fw_version'][0]}!")
                        if forced_update == True:
                            print("    the firmware will be overwritten. (Forced Overwrite Mode)")
                        else:
                            print("    update of this sensor was skipped.")
                            break

                    # Check the first 12-bytes H/W ID
                    target_hw_id = info[1]['sensor_hw_id'][0:12]
                    if list(target_hw_id) != list(item['sensor_id_arr']):
                        print("    the sensor_hw_id does not match the .bin file!")
                        print("    please contact the manufacturer.")
                        print("    update of this sensor was skipped.")
                        break

                    # Check the supported bootloader (FW0) version
                    fw_ver = info[1]['sensor_fw_ver'][2] * 10000 + info[1]['sensor_fw_ver'][1] * 100 + info[1]['sensor_fw_ver'][0]
                    if fw_ver < 10504:
                        print("    this sensor does not support firmware updates. (FW0 < V1.5.4)")
                        print("    please contact the manufacturer.")
                        print("    update of this sensor was skipped.")
                        break

                    # Check the target is in safeboot mode
                    if info[1]['sensor_boot_ctrl'] != 0:
                        print("    the sensor is not in safe-boot mode.")
                        print("    try to re-send safe-boot command to the sensor...", end='', flush=True)

                        # Re-try
                        tries = 3
                        error = True
                        for ip, sock in sockets.items():
                            if is_in_subnet(target_ip, ip, sock['subnet']):
                                while tries > 0:
                                    sock['config'].sendto(cmd_measure, (target_ip, sensor_config_port))
                                    time.sleep(1)

                                    sock['config'].sendto(cmd_safe_boot, (sock['broadcast'], sensor_config_port))
                                    for i in range(10):
                                        time.sleep(1)
                                        print('.', end='', flush=True)

                                    while error == True:
                                        sock['config'].sendto(cmd_read_info, (sock['broadcast'], sensor_config_port))
                                        
                                        # Try to read info
                                        for sock_read in sock['data']:
                                            while error == True:
                                                try:
                                                    data, sender = sock_read.recvfrom(2000)
                                                except OSError:
                                                    # There is no data in the socket buffer
                                                    break

                                                if len(data) == (166 + 8) and data[:6] == info_v2_header:
                                                    # Info_v2 packet was received
                                                    retry_info = decode_info_v2(data[6:172])
                                                    if retry_info['sensor_sn'] == item['sensor_sn']:
                                                        if retry_info['sensor_boot_ctrl'] == 0:
                                                            error = False
                                                        break
                                    
                                    tries = tries -1

                        if error == True:
                            print("    fail to safe-boot.")
                            print("    please turn off the sensor completely, then turn it back on and try again.")
                            break
                        else:
                            print("    success to safe-boot.")

                    # Check the configuration locker
                    if info[1]['lock'] != 0:
                        print("    the sensor has been locked (configuration locker).")
                        print("    please unlock the sensor by sending cmd_unlock.")
                        break
                    
                    if command == 'update':
                        print(f"    the sensor firmware {item['fw_type']} will be updated. (V{info[1]['sensor_fw1_ver'][2]}.{info[1]['sensor_fw1_ver'][1]}.{info[1]['sensor_fw1_ver'][0]} -> V{item['fw_version'][2]}.{item['fw_version'][1]}.{item['fw_version'][0]})")
                    elif command == 'overwrite':
                        print(f"    the sensor firmware {item['fw_type']} will be overwritten. (V{info[1]['sensor_fw1_ver'][2]}.{info[1]['sensor_fw1_ver'][1]}.{info[1]['sensor_fw1_ver'][0]} -> V{item['fw_version'][2]}.{item['fw_version'][1]}.{item['fw_version'][0]})") 
                    
                    time.sleep(0.1)
                    
                    # Send cmd_flash_start
                    print(f"    try to set the sensor to flashing mode...", end='', flush=True)
                    success = False
                    while success == False:
                        cmd_flash_start[8:10] = bytearray([info[1]['sensor_sn']%256, info[1]['sensor_sn']//256])
                        for ip, sock in sockets.items():
                            if is_in_subnet(target_ip, ip, sock['subnet']):
                                sock['config'].sendto(cmd_flash_start, (target_ip, sensor_config_port))

                                for i in range(3):
                                    time.sleep(1)
                                    print('.', end='', flush=True)
                                
                                flush_socket(sockData)
                                time.sleep(1)
                        
                                # read the ack
                                for sock_read in sock['data']:
                                    while success == False:
                                        try:
                                            flash_ack, sender = sock_read.recvfrom(2000)
                                        except OSError:
                                            # There is no data in the socket buffer
                                            break

                                        if sender[0] != target_ip:
                                            sockConfig.sendto(cmd_pause, (sender[0], sensor_config_port))
                                            continue

                                        if (len(flash_ack) == (34 + 8) and flash_ack[:6] == ack_header):
                                            is_all_zero = all(byte == 0 for byte in flash_ack[8:40])
                                            if is_all_zero:
                                                success = True
                                                break
                    
                    # Check error
                    if success == False:
                        print('')
                        print("    fail to set the sensor in flashing mode... (skipped)")
                        break

                    print('')
                    print("    success to set the flashing mode!")

                    # Send firmware data by using flash_block message
                    print(f"    try to download the firmware {item['fw_type']} V{item['fw_version'][2]}.{item['fw_version'][1]}.{item['fw_version'][0]} to the sensor #{info[1]['sensor_sn']}...")
                    prog_bar_str = "    [________________________________] "
                    print(prog_bar_str + "0.0 %", end="", flush=True)
                    with open("bin/" + item['file_name'], 'rb') as file:
                        for _o in range(256):
                            # Build flash_block
                            flash_head = flash_block_headder
                            flash_head = flash_head + bytearray(info[1]['sensor_hw_id'])
                            flash_head = flash_head + bytearray([2, 2, 0])
                            flash_head = flash_head + bytearray(item['fw_version'])

                            read_bin_data = file.read(1024)
                            
                            if not read_bin_data:
                                flash_body = bytearray([0xFF] * 1024)
                            elif len(read_bin_data) != 1024:
                                flash_body = read_bin_data + bytearray([0xFF] * (1024 - len(read_bin_data)))
                            else:
                                flash_body = read_bin_data

                            flash_crc16 = get_crc16(flash_body)

                            flash_head[38] = _o & 0xFF 

                            flash_block = flash_head + flash_body + bytearray([flash_crc16 & 0xFF, (flash_crc16 >> 8) & 0xFF]) + tail
                            while True:
                                # Send flash_block
                                for ip, sock in sockets.items():
                                    if is_in_subnet(target_ip, ip, sock['subnet']):
                                        sock['config'].sendto(flash_block, (target_ip, sensor_config_port))
                                
                                time.sleep(0.03)
                                
                                # read the ack
                                for ip, sock in sockets.items():
                                    if is_in_subnet(target_ip, ip, sock['subnet']):
                                        for sock_read in sock['data']:
                                            while True:
                                                try:
                                                    flash_ack, sender = sock_read.recvfrom(2000)
                                                except OSError:
                                                    # There is no data in the socket buffer
                                                    break
                                                except Exception as e:
                                                    continue

                                                if sender[0] != target_ip:
                                                    sock['config'].sendto(cmd_pause, (sock['broadcast'], sensor_config_port))
                                                    continue

                                                if (len(flash_ack) == (34 + 8) and flash_ack[:6] == ack_header):
                                                    break

                                # Check the ack
                                if (len(flash_ack) == (34 + 8) and flash_ack[:6] == ack_header):
                                    if _o < 256: # for indexing error
                                        if ((flash_ack[8 + (_o//8)] >> (_o%8)) & 0x01) == 0:
                                            continue
                                        else:
                                            break

                            if _o%8 == 0:
                                prog_bar_str = prog_bar_str.replace('_', '>', 1)
                                if _o//8 > 0:
                                    prog_bar_str = prog_bar_str.replace('>', '=', 1)

                            # Print
                            print("\r" + prog_bar_str + str(round((_o + 1)/2.56, 1)) + " %", end="", flush=True)

                    print("    ")
                    print("    success to download the firmware!")

                    # Sleep 200 msec
                    time.sleep(0.2)

                    # Send cmd_flash_finish
                    print("    try to flashing the firmware...", end='', flush=True)
                    cmd_flash_finish[8:10] = bytearray([info[1]['sensor_sn']%256, info[1]['sensor_sn']//256])
                    for ip, sock in sockets.items():
                        if is_in_subnet(target_ip, ip, sock['subnet']):
                            sock['config'].sendto(cmd_flash_finish, (target_ip, sensor_config_port))
                    for i in range(10):
                        time.sleep(1)
                        print('.', end='', flush=True)
                    
                    success = False
                    while success == False:
                        for ip, sock in sockets.items():
                            if is_in_subnet(target_ip, ip, sock['subnet']):
                                for sock_read in sock['data']:
                                    while True:
                                        try:
                                            check_flash, sender = sock_read.recvfrom(2000)
                                        except OSError:
                                            break
                                        except Exception as e:
                                            continue

                                        if sender[0] != target_ip:
                                            sock['config'].sendto(cmd_pause, (sender[0], sensor_config_port))
                                            continue

                                        if (len(check_flash) == (28 + 8) and check_flash[:6] == status_header) or (len(check_flash) == (312 + 8) and check_flash[:6] == status_full_header):
                                            sock['config'].sendto(cmd_read_info, (target_ip, sensor_config_port))
                                        
                                        elif len(check_flash) == (166 + 8) and check_flash[:6] == info_v2_header:
                                            reread_info_v2 = decode_info_v2(check_flash[6:172])
                                            if list(reread_info_v2['sensor_fw1_ver']) == list(item['fw_version']):
                                                success = True
                                            else:
                                                sock['config'].sendto(cmd_flash_finish, (target_ip, sensor_config_port))
                                                time.sleep(10)
                                            break

                        time.sleep(0.01)

                    # Check error
                    if success == False:
                        print('')
                        print("    fail to flash the sensor... (fail to read info)")
                        print("    please turn off the sensor completely, then turn it back on and try again.")
                        break

                    # Send cmd_pause to the sensor
                    for ip, sock in sockets.items():
                        if is_in_subnet(target_ip, ip, sock['subnet']):
                            sock['config'].sendto(cmd_pause, (target_ip, sensor_config_port))

                    print('')
                    print("    success to flash the firmware!")
                    print(f"    success to update the sensor #{item['sensor_sn']}!")

                    sensor_skipped.pop()
                    sensor_updated.append(item['sensor_sn'])

            time.sleep(0.3)

    print("Result:")
    if sensor_updated != []:
        if forced_update:
            print(f"  overwritten({len(sensor_updated)}): " + str(sensor_updated))
        else:
            print(f"  updated({len(sensor_updated)}): " + str(sensor_updated))
    if sensor_skipped != []:
        print(f"  skipped({len(sensor_skipped)}): " + str(sensor_skipped))
    
    # Send cmd_reboot to all
    print("Reboot all the connected LiDARs.", end='', flush=True)
    for ip, sock in sockets.items():
            sock['config'].sendto(cmd_reboot, (sock['broadcast'], sensor_config_port))
    for i in range(5):
        time.sleep(1)
        print('.', end='', flush=True)
    print('')

    print('Done!')

    # Close sockets
    for ip, item in sockets.items():
        for sock in item['data']:
            sock.close()
        item['config'].close()
    return

#### MAIN ENTRY POINT ####
if __name__ == '__main__':
    # Initial print
    print("ilidar-tool V" + ilidar_tool_version)

    # Initial variables
    host_ip_list = get_ip_list()
    if len(host_ip_list) == 0:
        print('Invalid network setup. There are no connections with IPv4...')
        print('')
        sys.exit()

    # Check the command
    if check_command(sys.argv) == False:
        print('')
        sys.exit()

    # Create the parser
    parser = argparse.ArgumentParser(add_help=False)

    # Add arguments
    parser.add_argument('-h', '--help',         action=custom_help_action, nargs=0)

    parser.add_argument('-i', '--info',         type=str, nargs='+')
    parser.add_argument('-p', '--pause',        type=str, nargs='+')
    parser.add_argument('-m', '--measure',      type=str, nargs='+')
    parser.add_argument('-l', '--lock',         type=str, nargs='+')
    parser.add_argument('-u', '--unlock',       type=str, nargs='+')
    parser.add_argument('-r', '--reboot',       type=str, nargs='+')
    parser.add_argument('-d', '--redirect',     type=str, nargs='+')

    parser.add_argument('--reset',              type=str, nargs='+')
    parser.add_argument('--config',             type=str, nargs='+')
    parser.add_argument('--convert',            type=str, nargs=2)
    parser.add_argument('--update',             type=str, nargs='+')
    parser.add_argument('--overwrite',          type=str, nargs='+')

    parser.add_argument('-S', '--sender',       type=str, nargs='+')
    parser.add_argument('-I', '--sender_ip',    type=str, nargs='+')
    parser.add_argument('-P', '--sender_port',  type=str, nargs='+')

    # Get args
    args = parser.parse_args()

    # Get command
    print('Command details:')
    command, arg_list = get_command(args)
    if command == '':
        print('Undefined command!')
        print('')
        sys.exit()
    print('  command:')
    print('    ' + command)

    # Get arguments and option
    print('  arguments:')
    if command == 'convert':
        file_list, file_len = parse_cvt_list(arg_list)

        if file_len != 2:
            print('  invalid arguments for the ' + command + 'command!')
            print('')
            sys.exit()
            
        file_msg = { 'command': command, 'file_list': file_list }

    elif command == 'config':
        file_list, file_len = parse_json_list(arg_list)

        if file_len == 0:
            print('  invalid arguments for the ' + command + 'command!')
            print('')
            sys.exit()

        file_msg = { 'command': command, 'file_list': file_list }

    else:
        target_type, target_list, target_len = parse_arg_list(arg_list)

        if target_len == 0:
            print('  invalid arguments for the ' + command + 'command!')
            print('')
            sys.exit()

        cmd_msg = { 'command': command, 'target_type': target_type, 'target_list': target_list }

    # Read listening list as dictonary form
    listening_list = {}

    if command != 'convert':
        if args.sender is None and args.sender_ip is None and args.sender_port is None:
            print('  option:')
            print('    None: Use all connected network interfaces (AF_INET)')

            # Read option input
            for single_ip in host_ip_list:
                single_subnet = get_subnet_mask(single_ip)
                single_broadcast_ip = get_broadcast_ip(single_ip, single_subnet)
                
                if single_ip in listening_list:
                    listening_list[single_ip]['port'].append(7256)
                else:
                    listening_list[single_ip] = {
                        'port': [7256],
                        'subnet': single_subnet,
                        'config': single_broadcast_ip
                    }

        elif args.sender is not None:
            print('  option:')
            print('    -S, --sender ' + str(args.sender))

            # Read option input
            for sender_option in args.sender:
                option_result, option_ip, option_port = check_option(sender_option)
                if option_result is True and option_ip != '':
                    option_subnet = get_subnet_mask(option_ip)
                    option_broadcast_ip = get_broadcast_ip(option_ip, option_subnet)
                    
                    if option_ip in listening_list:
                        listening_list[option_ip]['port'].append(7256)
                    else:
                        listening_list[option_ip] = {
                            'port': [option_port],
                            'subnet': option_subnet,
                            'config': option_broadcast_ip
                        }

        else:
            print('  option:')
            print('    -I, --sender_ip ' + str(args.sender_ip))
            print('    -P, --sender_port ' + str(args.sender_port))

            # Read option input
            if args.sender_ip is not None:
                for sender_option in args.sender_ip:
                    option_result, option_ip, option_port = check_option(sender_option)
                    if option_result is True and option_ip != '' and option_port == 7256:
                        option_subnet = get_subnet_mask(option_ip)
                        option_broadcast_ip = get_broadcast_ip(option_ip, option_subnet)
                        
                        if option_ip not in listening_list:
                            listening_list[option_ip] = {
                                'subnet': option_subnet,
                                'config': option_broadcast_ip
                            }
                    else:
                        print('    Invaild option: ' + sender_option + ' (Skipped)')
            else:
                # Use host_ip_list
                for single_ip in host_ip_list:
                    single_subnet = get_subnet_mask(single_ip)
                    single_broadcast_ip = get_broadcast_ip(single_ip, single_subnet)
                    
                    if single_ip not in listening_list:
                        listening_list[single_ip] = {
                            'subnet': single_subnet,
                            'config': single_broadcast_ip
                        }

            port_list = []
            port_num = 0
            if args.sender_port is not None:
                for sender_option in args.sender_port:
                    option_result, option_ip, option_port = check_option(sender_option)
                    if option_result is True and option_ip == '':
                        port_list.append(option_port)
                        port_num = port_num + 1
                    else:
                        print('    Invaild option: ' + sender_option + ' (Skipped)')
            else:
                # Use default
                port_list.append(7256)

            # Append ports to IPs
            for ip in listening_list:
                listening_list[ip]['port'] = port_list
            
        # Print
        ip_num = 0
        print('  interface:')
        for ip, item in listening_list.items():
            print('    Interface #' + str(ip_num) + ' ' + ip + ':' + str(item['port']))
            ip_num = ip_num + 1

        if ip_num == 0:
            print('    Invaild option error! Use --help to check the instruction.')
            print('')
            sys.exit()

        net_msg = { 'listening_list': listening_list }

    # Run the command functions
    if command == 'update':
        cmd_update_run(False, cmd_msg, net_msg)
    elif command == 'overwrite':
        cmd_update_run(True, cmd_msg, net_msg)
    elif command == 'convert':
        cmd_convert_run(file_msg)
    elif command == 'config':
        cmd_config_run(file_msg, net_msg)
    else:
        if 'SN' not in target_type:
            cmd_sendonly(cmd_msg, net_msg)
        else:
            cmd_run(cmd_msg, net_msg)

    print('')
    sys.exit()
