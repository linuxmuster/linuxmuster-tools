"""
Tests for DomCert, which fetches a peer certificate over a real TLS
connection and reports whether it is still valid / how long until it
expires.

Two flavours of tests are used:

- Real end-to-end tests against a local TLS server (via the
  `tls_server_factory` fixture) for the happy path, to prove the actual
  socket/TLS/parsing pipeline works.
- Fast unit tests that monkeypatch the private `_get_cert` network call
  to directly exercise the expiry-calculation/formatting logic
  (`_get_limit`, `isvalid`, `expires`) without any network dependency.
  This is also the only practical way to reach the "expired" branch of
  that logic -- see the note in
  `test_expired_cert_is_rejected_at_tls_handshake_before_app_logic_runs`.
"""

from datetime import datetime, timedelta, timezone

import pytest
import ssl

from linuxmusterTools.common.checks.certificates import DomCert


# ---------------------------------------------------------------------------
# Real end-to-end tests (actual socket + TLS handshake)
# ---------------------------------------------------------------------------

def test_domcert_valid_cert_end_to_end(tls_server_factory, utcnow):
    not_before = utcnow - timedelta(days=1)
    not_after = utcnow + timedelta(days=30)
    hostname, port = tls_server_factory(not_before, not_after)

    cert = DomCert(hostname, port)

    assert cert.isvalid() is True
    message = cert.expires()
    assert "days" in message
    assert "Expired" not in message


def test_domcert_captures_issuer_common_name_end_to_end(tls_server_factory, utcnow):
    not_before = utcnow - timedelta(days=1)
    not_after = utcnow + timedelta(days=30)
    hostname, port = tls_server_factory(not_before, not_after, issuer_cn="My Test Issuer")

    cert = DomCert(hostname, port)

    # ssl returns issuer as a tuple of tuples of (attribute, value) pairs.
    issuer_values = {value for rdn in cert.issuer for (_, value) in rdn}
    assert "My Test Issuer" in issuer_values


def test_expired_cert_is_rejected_at_tls_handshake_before_app_logic_runs(tls_server_factory, utcnow):
    """
    Documents actual behaviour: ssl.create_default_context() validates the
    certificate's validity dates itself during the TLS handshake. For a
    genuinely expired certificate this raises SSLCertVerificationError
    *before* DomCert ever gets a chance to inspect notAfter, so in real
    usage `DomCert(...)` raises instead of `isvalid()` gracefully
    returning False for an expired cert. See production bug note.
    """
    not_before = utcnow - timedelta(days=60)
    not_after = utcnow - timedelta(days=1)
    hostname, port = tls_server_factory(not_before, not_after)

    with pytest.raises(ssl.SSLCertVerificationError):
        DomCert(hostname, port)


def test_domcert_connection_failure_propagates():
    # Nothing is listening on this port -> the underlying connect() should
    # fail, and DomCert does not catch/wrap that exception.
    with pytest.raises(OSError):
        DomCert("127.0.0.1", 1)


# ---------------------------------------------------------------------------
# Unit tests for the expiry logic (network call replaced by a fake)
# ---------------------------------------------------------------------------

def _patch_fake_get_cert(monkeypatch, not_after_str, issuer=None):
    def _fake(self):
        self.cert = {
            "notAfter": not_after_str,
            "issuer": issuer or ((("commonName", "Test CA"),),),
        }
        self.issuer = self.cert["issuer"]

    monkeypatch.setattr(DomCert, "_get_cert", _fake)


def test_isvalid_true_for_future_notafter(monkeypatch):
    far_future = (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%b %d %H:%M:%S %Y GMT")
    _patch_fake_get_cert(monkeypatch, far_future)

    cert = DomCert("example.invalid", 443)

    assert cert.isvalid() is True
    assert "days" in cert.expires()
    assert far_future in cert.expires()


def test_isvalid_false_and_expired_message_for_past_notafter(monkeypatch):
    past = "Jan 01 00:00:00 2000 GMT"
    _patch_fake_get_cert(monkeypatch, past)

    cert = DomCert("example.invalid", 443)

    assert cert.isvalid() is False
    assert cert.expires() == f"Expired since {past}"


def test_notafter_format_must_match_expected_strptime_pattern(monkeypatch):
    # Sanity check that our fake payload uses the exact format DomCert
    # expects ("%b %d %H:%M:%S %Y GMT"), matching what Python's ssl module
    # actually returns for a peer certificate's notAfter field.
    valid_format = "Dec 31 23:59:59 2099 GMT"
    _patch_fake_get_cert(monkeypatch, valid_format)

    cert = DomCert("example.invalid", 443)

    assert cert.notAfter_timestamp == datetime.strptime(valid_format, "%b %d %H:%M:%S %Y GMT").replace(tzinfo=timezone.utc)


def test_load_raises_on_malformed_notafter(monkeypatch):
    _patch_fake_get_cert(monkeypatch, "not-a-date")

    with pytest.raises(ValueError):
        DomCert("example.invalid", 443)
