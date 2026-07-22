import sys
import os

# Ensure the package is importable when running pytest from this directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

import socket
import ssl
import threading
from datetime import datetime, timedelta, timezone

import pytest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

import linuxmusterTools.common.checks.certificates as certificates_module


def _generate_self_signed_cert(dns_name, not_before, not_after, issuer_cn=None):
    """
    Build a small self-signed certificate (acting as its own trust anchor)
    with a configurable validity window, so tests can exercise both a
    currently-valid and an already-expired certificate.

    `dns_name` goes into the SAN and must be a hostname the test client can
    actually resolve/connect to (e.g. "localhost"); `issuer_cn` is the
    subject/issuer common name and can be an arbitrary label used to assert
    that DomCert captures issuer information correctly.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_cn or dns_name)])

    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(dns_name)]), critical=False)
        .sign(key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem


class _TLSServer:
    """
    Minimal background TLS server used to give DomCert a real socket/TLS
    handshake to talk to, instead of mocking the network away entirely.
    """

    def __init__(self, cert_file, key_file):
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(str(cert_file), str(key_file))

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(0.5)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]

        self._stop = False
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while not self._stop:
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                with self.ctx.wrap_socket(conn, server_side=True) as ssl_conn:
                    try:
                        ssl_conn.recv(1)
                    except Exception:
                        pass
            except Exception:
                # Handshake failures (e.g. client rejected an expired cert)
                # are expected in some tests; the server just moves on.
                pass

    def stop(self):
        self._stop = True
        try:
            self.sock.close()
        except OSError:
            pass
        self.thread.join(timeout=2)


@pytest.fixture
def tls_server_factory(tmp_path, monkeypatch):
    """
    Factory fixture: tls_server_factory(not_before, not_after) -> (hostname, port)

    Spins up a real local TLS server presenting a self-signed certificate
    with the requested validity window, and patches
    certificates.ssl.create_default_context so the client trusts that
    certificate (standing in for the real system CA store).
    """
    created = []

    def _make(not_before, not_after, dns_name="localhost", issuer_cn=None):
        cert_pem, key_pem = _generate_self_signed_cert(dns_name, not_before, not_after, issuer_cn=issuer_cn)
        cert_file = tmp_path / f"server-{len(created)}.crt"
        key_file = tmp_path / f"server-{len(created)}.key"
        cert_file.write_bytes(cert_pem)
        key_file.write_bytes(key_pem)

        server = _TLSServer(cert_file, key_file)
        created.append(server)

        real_create_default_context = ssl.create_default_context

        def fake_create_default_context(*args, **kwargs):
            return real_create_default_context(cafile=str(cert_file))

        monkeypatch.setattr(certificates_module.ssl, "create_default_context", fake_create_default_context)

        return dns_name, server.port

    yield _make

    for server in created:
        server.stop()


@pytest.fixture
def utcnow():
    return datetime.now(timezone.utc)
