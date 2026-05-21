"""Environment variable parser tests"""

import pytest
from django.core.exceptions import ImproperlyConfigured

from main.envs import get_dict_of_str


def test_get_dict_of_str(mocker):
    """get_dict_of_str should parse a dictionary of string keys and values."""
    mocker.patch.dict(
        "os.environ",
        {
            "TEST_DICT": (
                '{"ocw-course-v3": "extra-theme-tracking-id&gtm_auth=fake", '
                '"theme": "alternate-theme-tracking-id"}'
            )
        },
    )

    assert get_dict_of_str("TEST_DICT", {}) == {
        "ocw-course-v3": "extra-theme-tracking-id&gtm_auth=fake",
        "theme": "alternate-theme-tracking-id",
    }


def test_get_dict_of_str_default(mocker):
    """get_dict_of_str should return the default if the variable is unset."""
    mocker.patch.dict("os.environ", {}, clear=True)

    assert get_dict_of_str("TEST_DICT", {"theme": "default-tracking-id"}) == {
        "theme": "default-tracking-id"
    }


@pytest.mark.parametrize(
    "value", ['["theme"]', '{"theme": 123}', '{1: "alternate-theme-tracking-id"}']
)
def test_get_dict_of_str_invalid(mocker, value):
    """get_dict_of_str should reject non-dictionary or non-string values."""
    mocker.patch.dict("os.environ", {"TEST_DICT": value})

    with pytest.raises(ImproperlyConfigured):
        get_dict_of_str("TEST_DICT", {})
