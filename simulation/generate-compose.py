import yaml
import random

"""""
# [+] Good thing
# [-] Usually Bad Thing
# [!] Error
"""""


# Number of slaves
NUM_SLAVES = 100

PHYSICAL_SUBNET = "192.168.0.0/24"  # True Subnet
PHYSICAL_GATEWAY = "192.168.0.1"    # Gateway IP address - Who to contact when wanting to communicate on network
PARENT_INTERFACE = "eth0"           # The physical network port on the Pi / Could use mac address here to make more resilient but not needed right now
BASE_IP = "192.168.0."              # Subnet IP start
START_IP = 100                      # Containers will get .100 through .109


# What each slave will simulate
profiles = ["tank", "motor", "pump", "valve", "silent"]

profile_weights = [24, 24, 24, 24, 4]


# Setup - Slaves will be put in here later
compose = {
    "version": "3.9",   # Version is outdated in docker and should be left out
    "services": {},     # Contains slaves

    # Network setup - Uses a vlan to make each slave contactable
    "networks": {
        "macvlan_net": {
            "driver": "macvlan",
            "driver_opts": {
                "parent": PARENT_INTERFACE
            },
            "ipam": {
                "config": [{"subnet": PHYSICAL_SUBNET, "gateway": PHYSICAL_GATEWAY}]
            }
        }
    }
}

# Inputs slaves into compose
for i in range(1, NUM_SLAVES + 1):

    # Setup chooses a profile and prepares the IP
    ip = f"{BASE_IP}{START_IP + i - 1}"

    # random.choices returns a list thats why we need [0] and k=1 is to return only one sample
    profile = random.choices(profiles, weights=profile_weights, k=1)[0]

    # In the compose access services field and input slave_i and the instructions for each slave on startup as well as network information
    # Also contains slave name, id, type which will be accesed later by the slave script
    compose["services"][f"slave_{i}"] = {
        "build": ".",
        "container_name": f"slave_{i}",
        "command": "python -u slave.py",
        "environment": [
            f"MODBUS_UNIT_ID={i}",
            f"SLAVE_NAME=PLC-{i:03}",
            f"PROCESS_TYPE={profile}",
        ],
        "networks": {
            "macvlan_net": {"ipv4_address": ip}
        },
        "restart": "unless-stopped"
    }

# Writes compose to docker-compose.yml - Overwrites existing data
with open("docker-compose.yml", "w") as f:
    yaml.dump(compose, f, sort_keys=False)

# Prints completion
print(f"[+] Macvlan docker-compose.yml generated.")