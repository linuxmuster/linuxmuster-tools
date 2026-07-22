"""
Tests for the SchoolError exception.
"""

import pytest

from linuxmusterTools.common.exceptions import SchoolError


def test_school_error_is_an_exception_subclass():
    assert issubclass(SchoolError, Exception)


def test_school_error_raisable_and_catchable_with_message():
    with pytest.raises(SchoolError) as excinfo:
        raise SchoolError("global is not a valid school scope")

    assert str(excinfo.value) == "global is not a valid school scope"
