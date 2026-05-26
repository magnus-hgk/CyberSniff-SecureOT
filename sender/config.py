import os
import ssl
from pathlib import Path


BASE_DIR  = Path(__file__).parent
CERTS_DIR = BASE_DIR / "certs"   


SERVER_HOST     = "Laptop-Receiver"       
SERVER_PORT     = 8443                 
SERVER_ENDPOINT = "/api/v1/logs"


CA_CERT     = CERTS_DIR / "ca.crt"      
SERVER_CERT = CERTS_DIR / "server.crt"  
SERVER_KEY  = CERTS_DIR / "server.key"  
CLIENT_CERT = CERTS_DIR / "client.crt"  
CLIENT_KEY  = CERTS_DIR / "client.key"  

SSL_PASSPHRASE = os.environ.get("SSL_PASSPHRASE", "1234")


TLS_MINIMUM_VERSION = ssl.TLSVersion.TLSv1_3

TLS13_CIPHER_SUITES = [
    "TLS_AES_256_GCM_SHA384",        
    "TLS_CHACHA20_POLY1305_SHA256",  
    "TLS_AES_128_GCM_SHA256",        
]


HMAC_ALGORITHM   = "sha256"
HMAC_HEADER_NAME = "X-Payload-HMAC"       
HASH_HEADER_NAME = "X-Payload-SHA256"     

HMAC_SECRET = os.environ.get("BRIDGE_HMAC_SECRET", "change-me-in-production").encode()