"""
Tests for the tiny tmp directory bootstrap helper.
"""

import linuxmusterTools.common.checks.tree as tree_module
from linuxmusterTools.common.checks.tree import check_tmp_dir


def test_creates_dir_and_sets_perms_when_missing(monkeypatch):
    calls = {}

    monkeypatch.setattr(tree_module.os.path, "exists", lambda p: False)
    monkeypatch.setattr(tree_module.os, "makedirs", lambda p: calls.setdefault("makedirs", p))
    monkeypatch.setattr(tree_module.os, "chmod", lambda p, mode: calls.setdefault("chmod", (p, mode)))

    check_tmp_dir()

    assert calls["makedirs"] == "/tmp/lmntool"
    assert calls["chmod"] == ("/tmp/lmntool", 0o600)


def test_does_nothing_when_dir_already_exists(monkeypatch):
    calls = {}

    monkeypatch.setattr(tree_module.os.path, "exists", lambda p: True)
    monkeypatch.setattr(tree_module.os, "makedirs", lambda p: calls.setdefault("makedirs", p))
    monkeypatch.setattr(tree_module.os, "chmod", lambda p, mode: calls.setdefault("chmod", (p, mode)))

    check_tmp_dir()

    assert "makedirs" not in calls
    assert "chmod" not in calls
