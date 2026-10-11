"""
Tests for the SchoolError, LdapNotProvisionedError, SchoolclassExistsError and
UnknownTemplateTypeError exceptions.
"""

import pytest

from linuxmusterTools.common.exceptions import (
    SchoolError,
    LdapNotProvisionedError,
    SchoolclassExistsError,
    UnknownTemplateTypeError,
)


def test_school_error_is_an_exception_subclass():
    assert issubclass(SchoolError, Exception)


def test_school_error_raisable_and_catchable_with_message():
    with pytest.raises(SchoolError) as excinfo:
        raise SchoolError("global is not a valid school scope")

    assert str(excinfo.value) == "global is not a valid school scope"


def test_ldap_not_provisioned_error_is_an_exception_subclass():
    assert issubclass(LdapNotProvisionedError, Exception)


def test_ldap_not_provisioned_error_raisable_and_catchable_with_message():
    with pytest.raises(LdapNotProvisionedError) as excinfo:
        raise LdapNotProvisionedError("setup.ini missing")

    assert str(excinfo.value) == "setup.ini missing"


def test_schoolclass_exists_error_is_an_exception_subclass():
    assert issubclass(SchoolclassExistsError, Exception)


def test_schoolclass_exists_error_raisable_and_catchable_with_message():
    with pytest.raises(SchoolclassExistsError) as excinfo:
        raise SchoolclassExistsError("The schoolclass 7a still exists in default-school")

    assert str(excinfo.value) == "The schoolclass 7a still exists in default-school"


def test_unknown_template_type_error_is_a_value_error_subclass():
    assert issubclass(UnknownTemplateTypeError, ValueError)
