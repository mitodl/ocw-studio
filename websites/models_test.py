""" Website models tests """
from websites.factories import WebsiteContentFactory


def test_websitecontent_calculate_checksum():
    """ Verify calculate_checksum() returns a sha256 checksum """
    content = WebsiteContentFactory.build(
        markdown="content", metadata={"data": "value"}
    )

    # manually computed checksum in a python shell
    assert (
        content.calculate_checksum()
        == "236c72d38543a9a7dc4cdd2bb9bf3e305b60598dfc2a8616e0429f9020692bed"
    )
