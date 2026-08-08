"""
Tests for is_samba_provisioned: detecting whether samba-tool domain provision
has actually run (not just whether linuxmuster-setup has started).
"""

from linuxmusterTools.common.provisioning import is_samba_provisioned


def test_is_samba_provisioned_false_when_admin_secret_missing(tmp_path):
    missing = tmp_path / "administrator"
    assert is_samba_provisioned(missing) is False


def test_is_samba_provisioned_true_when_admin_secret_present(tmp_path):
    present = tmp_path / "administrator"
    present.write_text("s3cr3t\n")
    assert is_samba_provisioned(present) is True


def test_is_samba_provisioned_default_path_is_admin_secret():
    from linuxmusterTools.common.provisioning import ADMIN_SECRET_PATH
    assert str(ADMIN_SECRET_PATH) == '/etc/linuxmuster/.secret/administrator'
