"""Unit tests for the error dictionary + envelope."""

import pytest

from app.core.errors import BizError, all_codes


def test_dictionary_loads_core_codes():
    codes = all_codes()
    for required in ("AUTH_INVALID_CREDENTIALS", "LICENSE_SEAT_EXCEEDED",
                     "LICENSE_BINDING_MISMATCH", "SYSTEM_INTERNAL_ERROR"):
        assert required in codes


def test_bizerror_envelope_bilingual():
    err = BizError("AUTH_INVALID_CREDENTIALS", {"attempts_left": 3})
    assert err.http_status == 401
    env_zh = err.envelope("req_1", "zh-CN")
    env_en = err.envelope("req_1", "en")
    assert env_zh["code"] == "AUTH_INVALID_CREDENTIALS"
    assert env_zh["message"] != env_en["message"]      # actually localized
    assert env_zh["details"] == {"attempts_left": 3}
    assert env_zh["request_id"] == "req_1"


def test_unknown_code_raises():
    with pytest.raises(KeyError):
        BizError("THIS_CODE_DOES_NOT_EXIST")


def test_license_codes_are_403():
    for code in ("LICENSE_REVOKED", "LICENSE_EXPIRED", "LICENSE_BINDING_MISMATCH",
                 "LICENSE_SEAT_EXCEEDED", "LICENSE_INVALID_SIGNATURE"):
        assert BizError(code).http_status == 403
