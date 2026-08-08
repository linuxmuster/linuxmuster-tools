from pathlib import Path

ADMIN_SECRET_PATH = Path('/etc/linuxmuster/.secret/administrator')


def is_samba_provisioned(admin_secret_path=ADMIN_SECRET_PATH):
    """
    Return True once samba-tool domain provision has run.

    Checks for the AD administrator secret (linuxmuster-setup's
    j_samba-provisioning module writes it right before calling
    'samba-tool domain provision') rather than /var/lib/linuxmuster/setup.ini:
    that file is written by the setup's very first module, well before Samba
    is touched, so it exists for most of the setup run while LDAP is still
    unusable.
    """


    return admin_secret_path.exists()
