"""Unit tests for password hashing + policy."""

import pytest

from app.core import security
from app.core.errors import BizError


def test_hash_and_verify():
    h = security.hash_password("Str0ngP@ssw0rd!")
    assert h != "Str0ngP@ssw0rd!"          # never plaintext
    assert security.verify_password("Str0ngP@ssw0rd!", h) is True
    assert security.verify_password("wrong", h) is False


def test_policy_min_length():
    with pytest.raises(BizError) as e:
        security.validate_password_policy("Ab1!", min_length=12, email="a@b.com", username="admin")
    assert e.value.code == "AUTH_PASSWORD_WEAK"


def test_policy_char_classes():
    with pytest.raises(BizError):
        security.validate_password_policy("alllowercaseletters", min_length=12,
                                          email="a@b.com", username="admin")


def test_policy_rejects_common_and_identity():
    with pytest.raises(BizError):
        security.validate_password_policy("password", min_length=8, email="a@b.com", username="admin")


def test_policy_accepts_strong():
    security.validate_password_policy("Str0ngP@ssw0rd!", min_length=12,
                                      email="forge@navtra.ai", username="Admin")


def test_constant_time_equals():
    assert security.constant_time_equals("abc", "abc") is True
    assert security.constant_time_equals("abc", "abd") is False
