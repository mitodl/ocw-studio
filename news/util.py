"""Utility functions for interacting with OCW News"""

import re

from bs4 import BeautifulSoup


def get_original_image_link(url):
    """
    Parse the image URL to cut off the 150x150 from the RSS feed

    Args:
        url (str): The image URL

    Returns:
        str: The updated URL if it matches the regex, else the original URL
    """
    match = re.match(r"^(?P<prefix>.+)-150x150\.(?P<suffix>.+)$", url)
    if match:
        return f"{match.group('prefix')}.{match.group('suffix')}"
    return url


def strip_namespace(tag):
    """
    Remove the namespace from a tag if it's present

    Args:
        tag (str): An XML tag

    Returns:
        str: The XML tag without a namespace prefix, or the same tag if no namespace prefix exists
    """  # noqa: E501
    if tag.startswith("{"):
        rindex = tag.find("}")
        return tag[rindex + 1 :]
    return tag


def serialize_item(item):
    """
    Serialize an RSS feed item

    Args:
        item (xml.etree.elementTree.Element): An <item>

    Returns:
        dict: A dictionary representation of the RSS item
    """
    obj = {
        strip_namespace(child.tag): {"text": child.text, **child.attrib}
        for child in item
    }
    description = obj["description"]
    soup = BeautifulSoup(description["text"], features="html.parser")
    images = soup.find_all("img")
    if images:
        image = images[0]
        src = get_original_image_link(image.get("src"))
        obj["image"] = src
    return obj


def rss_to_json(root):
    """
    Convert ETree representation of RSS to a list which is serializable to JSON for use with ocw-www

    Args:
        root (xml.etree.ElementTree.Element): The root element of the RSS feed

    Returns:
        list: A list representing the RSS feed which can be serialized to JSON
    """  # noqa: E501
    return [serialize_item(item) for item in root.iter(tag="item")]
