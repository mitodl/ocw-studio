"""Tests for utility functions for OCW News"""
import xml.etree.ElementTree as ET

import pytest

from news.util import (
    rss_to_json,
    serialize_item,
    get_original_image_link,
)


def test_rss_to_json(mocker):
    """
    rss_to_json should convert an Element which is the root of the RSS feed to something that can be serialized to JSON
    """
    item = {"a": "dictionary"}
    mocker.patch("news.util.serialize_item", return_value=item)
    root = ET.fromstring("<rss> <item /> <item /> </rss>")
    output = rss_to_json(root)
    assert output == [item, item]


@pytest.mark.parametrize("has_image", [True, False])
def test_serialize_item(has_image):
    """
    serialize_item should create a dictionary representation of the RSS feed item
    """
    example_description = f"""{"<![CDATA[<img src='http://example.com/image' />]]>" if has_image else ""}
        EPISODE SUMMARY In this episode, Senior Lecturer Emeritus Christopher Terman
        describes strategies for engaging students in hands-on learning in 6.004 Computation Structures.
        TRANSCRIPT EPISODE NOTES You...
        """
    example_item = f"""<rss xmlns:ns4="http://wellformedweb.org/CommentAPI/" version="2.0">
    <item>
        <title>
        Chalk Radio Podcast: Hands-On, Minds On with Dr. Christopher Terman
        </title>
        <description>{example_description}</description>
        <ns4:commentRss>
        https://www.ocw-openmatters.org/2020/12/09/chalk-radio-podcast
        </ns4:commentRss>
    </item></rss>"""
    item = ET.fromstring(example_item)

    output = serialize_item(item.find("item"))
    assert output["title"] == {
        "text": "\n        Chalk Radio Podcast: Hands-On, Minds On with Dr. Christopher Terman\n        "
    }
    if has_image:
        assert output["image"] == "http://example.com/image"
    else:
        assert "image" not in output

    assert output["commentRss"] == {
        "text": "\n        https://www.ocw-openmatters.org/2020/12/09/chalk-radio-podcast\n        "
    }


@pytest.mark.parametrize(
    "input_url, output_url",
    [
        [
            "https://www.ocw-openmatters.org/wp-content/uploads/2014/09/Open_Matters_Blog_Placeholder_Image-01-150x150.png",
            "https://www.ocw-openmatters.org/wp-content/uploads/2014/09/Open_Matters_Blog_Placeholder_Image-01.png",
        ],
        [
            "https://www.ocw-openmatters.org/wp-content/uploads/2014/09/Open_Matters_Blog_Placeholder_Image-01-150x150.jpg",
            "https://www.ocw-openmatters.org/wp-content/uploads/2014/09/Open_Matters_Blog_Placeholder_Image-01.jpg",
        ],
        ["https://example.com/image.jpg", "https://example.com/image.jpg"],
    ],
)
def test_get_original_image_link(input_url, output_url):
    """get_original_image_link should parse the image link and cut the 150x150 suffix from it"""
    assert get_original_image_link(input_url) == output_url
