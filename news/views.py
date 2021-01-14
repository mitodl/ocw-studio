"""Views related to OCW News"""
import xml.etree.ElementTree as ET

from django.http import JsonResponse
import requests

from news.util import rss_to_json


def news(request):
    """Fetch OCW News from their REST API and convert to a JSON format for use in ocw-www"""
    # This view should only be triggered at build-time for ocw-www so there is no need to cache here
    news_url = "https://www.ocw-openmatters.org/feed/"

    resp = requests.get(news_url)
    resp.raise_for_status()
    root = ET.fromstring(resp.content.decode())
    items = rss_to_json(root)
    return JsonResponse({"items": items})
