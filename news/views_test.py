"""Views for OCW News"""
import json

import pytest
from django.urls import reverse


pytestmark = pytest.mark.django_db


def test_news(client, mocker):
    """
    The news API should return a JSON representation of the OCW News RSS Feed
    """
    some_xml = "<xml></xml>"
    some_json = {"xml": {"text": ""}}
    get_mock = mocker.patch("requests.get")
    get_mock.return_value.content = some_xml.encode()
    mocker.patch("news.views.rss_to_json", return_value=some_json)

    resp = client.get(reverse("ocw-news"))
    assert resp.content == json.dumps({"items": some_json}).encode()
    get_mock.return_value.raise_for_status.assert_called_once_with()
