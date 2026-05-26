import json
import os
import struct
from scapy.all import sniff, IP, TCP, Raw

"""""
# [+] Good thing
# [-] Usually Bad Thing
# [!] Error
"""""

# This is the interface we are sniffing on, we could use the MAC address here for the ethernet port if the interface changes name but theres no need right now
INTERFACE = "eth0"
LOG_NAME = "LOG_FILE.jsonl"
BUFFER_SIZE = 1000

# We use a class to define the variables we need and to avoid global variables. Contains everything we need
class ModbusSniffer:
    # When the class is created we pass in LOG_NAME and BUFFER_SIZE
    def __init__(self, filename, buffer_limit):
        self.filename = filename
        self.buffer_limit = buffer_limit
        # Packet array to hold packets that have been parsed until ready to passs them to file
        self.packet_buffer = []
        self.file_handle = open(self.filename, 'a')

        # Give read/write for the log to the sniffer user
        try:
            import pwd
            import grp
            uid = pwd.getpwnam("sniffer").pw_uid
            gid = grp.getgrnam("sniffer").gr_gid
            os.chown(self.filename, uid, gid)
            os.chmod(self.filename, 0o664) # Read/Write for owner & group - read for others
            print(f"[+] Successfully set ownership of {self.filename} to sniffer:sniffer")
        except Exception as e:
            print(f"[!] Could not adjust file ownership permissions: {e}")

        self.packet_count = 0

    def parse_modbus_header(self, payload):
        # Checks if the packet is too small or if its fragmented
        if len(payload) < 8:
            return None

        try:
            trans_id, proto_id, length, unit_id, func_code = struct.unpack('>HHHBB', payload[:8])

            # returns entry of transaction id, unit id, function code and byte length
            return {
                "trans_id": trans_id,
                "unit_id": unit_id,
                "func_code": func_code,
                "byte_len": length
            }
        except struct.error:
            return None

    def process_packet(self, pkt):
        # Checks the packet for IP, TCP and Raw data and if it contains all three it is then passed to a payload variable to be manipulated
        if pkt.haslayer(IP) and pkt.haslayer(TCP) and pkt.haslayer(Raw):
            payload = pkt[Raw].load

            # Checks if the packet looks like modbus TCP, and if it does not it skips the packet
            if len(payload) >= 8 and payload[2:4] != b'\x00\x00':
                return

            # Calls above functions and parses modbus data into a transaction id, unit id, function code and byte length of the data
            modbus_data = self.parse_modbus_header(payload)


            # Creates an entry for the log file
            entry = {
                "ts": float(pkt.time),  # timestamp
                "src": pkt[IP].src,     # source IP
                "dst": pkt[IP].dst,     # destination IP
                "stream": f"{pkt[IP].src}:{pkt[TCP].sport}->{pkt[IP].dst}:{pkt[TCP].dport}", # packet stream from source to destination
                "modbus": modbus_data,  # modbus information - usually from FC17 or FC43
                "raw": payload.hex()
            }

            self.packet_buffer.append(json.dumps(entry) + '\n')
            self.packet_count += 1

            # Peridically writes the logs to the log file if the number of packets exceeds buffer_limit which is set at the top (1000)
            if len(self.packet_buffer) >= self.buffer_limit:
                self.file_handle.writelines(self.packet_buffer)
                self.file_handle.flush() # Forces the entries to be written
                self.packet_buffer = []
                print(f"[+] Flushed {self.buffer_limit} packets to disk. (Total: {self.packet_count})")

    def close(self):
        if self.packet_buffer:
            self.file_handle.writelines(self.packet_buffer)
        self.file_handle.close()
        print(f"\n[+] Capture stopped. Total packets logged: {self.packet_count}")

if __name__ == "__main__":
    sniffer = ModbusSniffer(LOG_NAME, BUFFER_SIZE)
    print(f"[+] Capture started on {INTERFACE}...")
    print("[-] Press Ctrl+C to stop.")

    try:
        # Starts the sniffing process on interface eth0 and passes all packets to the process_packet() function
        sniff(iface=INTERFACE, filter="tcp port 502", prn=sniffer.process_packet, store=0)
    except KeyboardInterrupt:
        pass
    finally:
        sniffer.close()