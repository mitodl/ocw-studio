"""Views related to OCW News"""
import xml.etree.ElementTree as ET  # noqa: N817

import requests
from django.http import JsonResponse

from news.util import rss_to_json


def news(request):  # noqa: ARG001
    """Fetch OCW News from their REST API and convert to a JSON format for use in ocw-www"""  # noqa: E501
    # This view should only be triggered at build-time for ocw-www so there is no need to cache here  # noqa: E501
    news_url = "https://www.ocw-openmatters.org/feed/"

    resp = requests.get(news_url, timeout=60)
    resp.raise_for_status()
    root = ET.fromstring(resp.content.decode())  # noqa: S314
    items = rss_to_json(root)
    return JsonResponse({"items": items})
