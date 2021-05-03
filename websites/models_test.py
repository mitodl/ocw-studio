""" Website models tests """
from websites.factories import WebsiteContentFactory


def test_websitecontent_calculate_checksum():
    """ Verify calculate_checksum() returns a sha256 checksum """
    content = WebsiteContentFactory.build(
        markdown="content", metadata={"data": "value"}, content_filepath="_index.md"
    )

    # manually computed checksum in a python shell
    assert (
        content.calculate_checksum()
        == "cfcbebb93fdf56848f32afc3d1bda55868a465547de0e6fb4b8dab05b69ec352"
    )
