"""Tests for feature_flag middleware"""

import pytest

from main.middleware import (
    CookieFeatureFlagMiddleware,
    QueryStringFeatureFlagMiddleware,
)
from main.utils import FeatureFlag

FEATURE_FLAG_COOKIE_NAME = "TEST_COOKIE"
FEATURE_FLAG_COOKIE_MAX_AGE_SECONDS = 60


@pytest.fixture()
def middleware_settings(settings):  # noqa: PT004
    """Default settings for middleware"""  # noqa: D401
    settings.MIDDLEWARE_FEATURE_FLAG_QS_PREFIX = "ZZ"
    settings.MIDDLEWARE_FEATURE_FLAG_COOKIE_NAME = FEATURE_FLAG_COOKIE_NAME
    settings.MIDDLEWARE_FEATURE_FLAG_COOKIE_MAX_AGE_SECONDS = (
        FEATURE_FLAG_COOKIE_MAX_AGE_SECONDS
    )


@pytest.fixture()
def qs_middleware(mocker, middleware_settings):  # pylint: disable=unused-argument
    """Mocked middleware for QueryStringFeatureFlagMiddleware"""  # noqa: D401
    return QueryStringFeatureFlagMiddleware(mocker.Mock())


@pytest.fixture()
def cookie_middleware(mocker, middleware_settings):  # pylint: disable=unused-argument
    """Mocked middleware for QueryStringFeatureFlagMiddleware"""  # noqa: D401
    return CookieFeatureFlagMiddleware(mocker.Mock())


def test_get_flag_key(qs_middleware):
    """Test get_flag_key"""
    assert qs_middleware.get_flag_key("EXAMPLE_FEATURE") == "ZZ_FEATURE_EXAMPLE_FEATURE"


def test_encode_feature_flags(qs_middleware):
    """Test that feature flags are encoded correctly"""
    assert qs_middleware.encode_feature_flags(None) == "0"
    assert qs_middleware.encode_feature_flags({"ZZ_FEATURE_NOTHING": 1}) == "0"

    assert qs_middleware.encode_feature_flags({"ZZ_FEATURE_EXAMPLE_FEATURE": 1}) == "1"


@pytest.mark.parametrize("get_value", [None, {}])
def test_process_request_no_qs(qs_middleware, mocker, get_value):
    """Test that no feature flag query string is a no-op"""
    request = mocker.Mock()
    request.GET = get_value
    assert qs_middleware(request) == qs_middleware.get_response.return_value


def test_process_request_clear(qs_middleware, mocker):
    """Test that it clears feature flags and redirect back to same path"""
    redirect_mock = mocker.patch("django.shortcuts.redirect")
    request = mocker.Mock()
    request.GET = {"ZZ_FEATURE_CLEAR": 1}
    request.path = "/dashboard/"
    assert qs_middleware(request) == redirect_mock.return_value

    redirect_mock.assert_called_once_with("/dashboard/")

    response = redirect_mock.return_value
    response.delete_cookie.assert_called_once_with(FEATURE_FLAG_COOKIE_NAME)


def test_process_request_query(qs_middleware, mocker):
    """Test that a feature flag is added correctly"""
    redirect_mock = mocker.patch("django.shortcuts.redirect")
    request = mocker.Mock()
    request.GET = {"ZZ_FEATURE_EXAMPLE_FEATURE": 1}
    request.path = "/dashboard/"
    assert qs_middleware(request) == redirect_mock.return_value

    redirect_mock.assert_called_once_with("/dashboard/")
    qs_middleware.get_response.assert_not_called()

    response = redirect_mock.return_value
    response.set_signed_cookie.assert_called_once_with(
        FEATURE_FLAG_COOKIE_NAME,
        "1",
        max_age=FEATURE_FLAG_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
    )


def test_decode_feature_flags(cookie_middleware):
    """Test that it decodes feature flags correctly"""
    assert cookie_middleware.decode_feature_flags(0) == set()
    assert cookie_middleware.decode_feature_flags(1) == {FeatureFlag.EXAMPLE_FEATURE}


def test_process_request_valid_cookie(cookie_middleware, mocker):
    """Test that a valid cookie results in the feature flags being set on request"""
    request = mocker.Mock()
    request.COOKIES = {FEATURE_FLAG_COOKIE_NAME: 1}
    request.get_signed_cookie.return_value = 1
    assert cookie_middleware(request) == cookie_middleware.get_response.return_value
    assert request.main_feature_flags == {FeatureFlag.EXAMPLE_FEATURE}
    request.get_signed_cookie.assert_called_once_with(FEATURE_FLAG_COOKIE_NAME)


def test_process_request_invalid_cookie(cookie_middleware, mocker):
    """Test that nothing fails if there is an invalid cookie"""
    request = mocker.Mock()
    request.COOKIES = {FEATURE_FLAG_COOKIE_NAME: 1}
    request.get_signed_cookie.side_effect = ValueError
    assert cookie_middleware(request) == cookie_middleware.get_response.return_value
    assert request.main_feature_flags == set()
    request.get_signed_cookie.assert_called_once_with(FEATURE_FLAG_COOKIE_NAME)


def test_process_request_no_cookie(cookie_middleware, mocker):
    """Test that nothing fails if there is no cookie"""
    request = mocker.Mock()
    request.COOKIES = {}
    assert cookie_middleware(request) == cookie_middleware.get_response.return_value
    request.get_signed_cookie.assert_not_called()
    assert request.main_feature_flags == set()
