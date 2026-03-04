import os


def check_tmp_dir():
    # Ensure tmp directory is ready
    if not os.path.exists('/tmp/lmntool'):
        os.makedirs('/tmp/lmntool')
        os.chmod('/tmp/lmntool', 0o600)