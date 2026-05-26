import datetime
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from config import CERTS_DIR, CA_CERT, SERVER_CERT, SERVER_KEY, CLIENT_CERT, CLIENT_KEY, SSL_PASSPHRASE, SERVER_HOST

KEY_SIZE    = 4096        
LEAF_SIZE   = 2048
CA_DAYS     = 3650
LEAF_DAYS   = 365         
COUNTRY     = "DK"
ORG         = ""
CA_CN       = "Secure-Data-Root-CA"
SERVER_CN   = "Laptop-Receiver"           
CLIENT_CN   = "Pi-Sender"  


def _generate_rsa_key(key_size: int = 2048) -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=key_size)

def _save_private_key(key: rsa.RSAPrivateKey, path: Path) -> None:
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(SSL_PASSPHRASE.encode()),
        )
    )
    # Modify permissions for certificate to read/write
    path.chmod(0o600)

def _save_cert(cert: x509.Certificate, path: Path) -> None:
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _subject(cn: str) -> x509.Name:
    return x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, COUNTRY),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, ORG),
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
    ])

def generate_ca() -> tuple:
    ca_key = _generate_rsa_key(KEY_SIZE)

    now = datetime.datetime.now(datetime.timezone.utc)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(_subject(CA_CN))
        .issuer_name(_subject(CA_CN))          
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=CA_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_cert_sign=True, crl_sign=True,
                content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False,
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    return ca_key, ca_cert

def generate_leaf_cert(cn: str, ca_key: rsa.RSAPrivateKey, ca_cert: x509.Certificate, is_server: bool = True, san_dns: list[str] | None = None, san_ips: list[str] | None = None) -> tuple:
    leaf_key = _generate_rsa_key(LEAF_SIZE)

    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(_subject(cn))
        .issuer_name(ca_cert.subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=LEAF_DAYS))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
    )

    if is_server:
        eku = x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.SERVER_AUTH])
        
        san_list = []
        if san_dns:
            san_list.extend([x509.DNSName(name) for name in san_dns])
        if san_ips:
            san_list.extend([x509.IPAddress(ipaddress.ip_address(ip)) for ip in san_ips])
            
        builder = builder.add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        )
    else:
        eku = x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.CLIENT_AUTH])

    builder = builder.add_extension(eku, critical=False)
    builder = builder.add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()), critical=False)
    builder = builder.add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)

    leaf_cert = builder.sign(ca_key, hashes.SHA256())
    return leaf_key, leaf_cert

def main() -> None:

    if CERTS_DIR.exists():
        import shutil
        shutil.rmtree(CERTS_DIR) 
    CERTS_DIR.mkdir(parents=True, exist_ok=True)

    ca_key, ca_cert = generate_ca()
    _save_private_key(ca_key,  CERTS_DIR / "ca.key")   
    _save_cert(ca_cert, CA_CERT)

    srv_key, srv_cert = generate_leaf_cert(
        cn=SERVER_CN, 
        ca_key=ca_key, 
        ca_cert=ca_cert,
        is_server=True, 
        san_dns=[SERVER_CN, "localhost"],
        san_ips=[SERVER_HOST, "127.0.0.1"]
    )
    _save_private_key(srv_key,  SERVER_KEY)
    _save_cert(srv_cert, SERVER_CERT)

    cli_key, cli_cert = generate_leaf_cert(
        cn=CLIENT_CN, ca_key=ca_key, ca_cert=ca_cert, is_server=False,
    )
    _save_private_key(cli_key, CLIENT_KEY)
    _save_cert(cli_cert, CLIENT_CERT)

    print("\n[+] Certificates Generated")

if __name__ == "__main__":
    main()