from pymodbus.client import ModbusTcpClient
import time
import random
"""""
# [+] Good thing
# [-] Usually Bad Thing
# [!] Error
"""""

# Initialize number of slaves
NUM_SLAVES = 100
BASE_IP = "192.168.0."
START_IP = 100

# Startup sequence - Connects to the slaves and discovers the network of slaves
def initialize_network(clients):
    print("--- Initiating Network Discovery ---")

    real_slaves = []



    # For each client set ip, unit id and client and try to connect.
    for client_data in clients:
        ip = client_data['ip']
        unit_id = client_data['unit_id']
        client = client_data['client']

        # If connection established read device information (read code 2 returns more data)
        if client.connect():
            try:
                ident = client.read_device_information(read_code=2, slave=unit_id)
                if not ident.isError():
                    vendor = ident.information.get(0, b"Unknown").decode('ascii', errors='ignore')
                    p_name = ident.information.get(3, b"Unknown").decode('ascii', errors='ignore')


                    if vendor == "Unknown" or "Generic" in p_name:
                        print(f"[+] Discovered shadow device: Adding to no-contact list")
                    else:
                        print(f"[+] Discovered {ip} (ID: {unit_id}): {vendor} - {p_name}")
                        real_slaves.append(client_data)

                else:
                    # If connectoin established but identification fails. Print which IP rejected the FC
                    print(f"[-] {ip} rejected FC43.")
            # Error handling - If connection is established and we run into an unexpected error.
            except Exception as e:
                print(f"[!] Error discovering {ip}: {e}")
        # If could not connect - Print could not connect
        else:
            print(f"[!] Could not connect to {ip}")
    print("--- Discovery Complete ---\n")
    return real_slaves


# Master function - Initializes Network Discovery and primary polling loop
def run_master():

    # Initialize client array - Contains slaves as a small array of ip, unit id and client
    clients = []
    for i in range(NUM_SLAVES):
        ip = f"{BASE_IP}{START_IP + i}"
        unit_id = i + 1
        clients.append({
            'ip': ip,
            'unit_id': unit_id,
            'client': ModbusTcpClient(ip, port=502, timeout=2)
        })

    # Function defined above - Starts Network Discovery and establishes connection to perform device identification
    active_devices = initialize_network(clients)

    # Counter to poll slaves more realistically
    counter = 0
    try:
        print("--- Entering Control Loop ---")

        # Do this until stopped
        while True:

            # For each slave try to connect and poll for data
            for client_data in active_devices:
                client = client_data['client']
                unit_id = client_data['unit_id']

                # If socket is already open we are connected
                if not client.is_socket_open():
                    client.connect()

                # Always read holding registers
                try:
                    rr = client.read_holding_registers(address=0, count=5, slave=unit_id)

                    # If polling number is even read discrete inputs
                    if counter % 2 == 0:
                        client.read_discrete_inputs(address=0, count=8, slave=unit_id)

                    # If counter is a multiple of 5 read input registers
                    if counter % 5 == 0:
                        client.read_input_registers(address=10, count=2, slave=unit_id)

                    # If read registers does not fail prepare values for write
                    if not rr.isError():
                        val = rr.registers[0]
                        # Reverses state
                        coil_state = (val % 2 == 0)
                        client.write_coil(address=0, value=coil_state, slave=unit_id)
                        client.write_registers(address=10, values=[val+1, val+2], slave=unit_id)
                # Error handling - Just pass to make sure program does not crash on an error
                except Exception:
                    pass
            # Network Jitter
            time.sleep(max(0.1, 0.5 + random.uniform(-0.1, 0.2)))
            counter += 1

    # When program is stopped by Ctrl+C print this
    except KeyboardInterrupt:
        print("\nStopping PLC Simulation")

    # Then close each client
    finally:
        for client_data in clients:
            client_data['client'].close()

# Run the thing
if __name__ == "__main__":
    run_master()