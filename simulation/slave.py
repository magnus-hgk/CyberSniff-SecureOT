import os
import threading
import time
import random
from pymodbus.server import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

"""""
# [+] Good thing
# [-] Usually Bad Thing
# [!] Error
"""""
# Network setup - Where to listen and how fast to update slave values
LISTEN_IP = "0.0.0.0" # Could be changed to 192.168.0.11
LISTEN_PORT = 502
UPDATE_INTERVAL = 1.0

# Read environment values from Docker environment
UNIT_ID = int(os.environ.get("MODBUS_UNIT_ID", 1))
SLAVE_NAME = os.environ.get("SLAVE_NAME", "PLC-DEFAULT")
PROCESS_TYPE = os.environ.get("PROCESS_TYPE", "generic")


# Update values script - With drift to simulate realism
def update_values(context):
    print(f"[+] Starting physics drift for {SLAVE_NAME} ({PROCESS_TYPE})")


    # Sets drift ranges for tank, motor, pump and valve
    drift_range = 5
    if PROCESS_TYPE == "tank": drift_range = 2
    elif PROCESS_TYPE == "motor": drift_range = 15
    elif PROCESS_TYPE == "valve": drift_range = 0

    # Run forever
    while True:

        # Set Context from docker-compose
        slave_ctx = context[UNIT_ID]
        current_values = slave_ctx.getValues(3, 0, count=3)

        # Drifts values
        new_values = [max(0, min(65535, val + random.randint(-drift_range, drift_range))) for val in current_values]
        slave_ctx.setValues(3, 0, new_values)

        # 20% of the time turns valve or pump either on or off based on current state
        if PROCESS_TYPE in ["valve", "pump"] and random.random() > 0.8:
            current_coil = slave_ctx.getValues(1, 0, count=1)[0]
            slave_ctx.setValues(1, 0, [not current_coil])

        # Sleeps for 1 second
        time.sleep(UPDATE_INTERVAL)

def run_slave():
    # Logging info for debugging
    print(f"[+] Booting {SLAVE_NAME} - Unit ID: {UNIT_ID}")

    # Creates a modbus slave with storage
    slave_store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0] * 100),                             # Read-only bits equivalent to bit[100] | Read-only bits - Usually sensor states or booleans
        co=ModbusSequentialDataBlock(0, [0] * 100),                             # Read/write bits                       | Writable bits - Usually motor/pump/valve on/off
        hr=ModbusSequentialDataBlock(0, [250, 5000, (UNIT_ID * 100)] + [0]*97), # Read/write 16-bit values              | Writable 16 bits - First three are initialized as 250, 5000 and UNIT_ID * 100, the rest are 0 | Usually temperature, water level, pressure etc.
        ir=ModbusSequentialDataBlock(0, [0] * 100)                              # Read-only 16-bit values               | Read-only 16 bits - Usually used for readings, analog measurements, target values, counters etc.
    )

    # Creates the device
    context = ModbusServerContext(slaves={UNIT_ID: slave_store}, single=False)


    # Sets identity values for FC 17 and/or FC43 depending on whether it's a silent device or a real device
    identity = ModbusDeviceIdentification()
    if PROCESS_TYPE == "silent":
        identity.VendorName = 'Unkown'
        identity.ProductCode = 'DEFAULT'
        identity.VendorUrl = ''
        identity.ProductName = 'Generic TCP Node'
        identity.ModelName = 'Unkown'
        identity.MajorMinorRevision = '1.0'
    else:
        identity.VendorName = 'OT-Sniffer-Lab'
        identity.ProductCode = f'SIM-{PROCESS_TYPE.upper()}'
        identity.VendorUrl = 'http://cybersniff.security.'
        identity.ProductName = f'{PROCESS_TYPE.capitalize()} Controller'
        identity.ModelName = SLAVE_NAME
        identity.MajorMinorRevision = '2.0.0'

    # Starts the update_values() on a new thread
    if not PROCESS_TYPE == "silent":
        threading.Thread(target=update_values, args=(context,), daemon=True).start()
    else:
        print(f"[+] Starting {SLAVE_NAME} as a silent device.")
    # Starts the modbus slave
    StartTcpServer(context=context, identity=identity, address=(LISTEN_IP, LISTEN_PORT))
    print(f"[+] Started slave_{UNIT_ID} - Listening on {LISTEN_IP}:{LISTEN_PORT}...")

if __name__ == "__main__":
    run_slave()