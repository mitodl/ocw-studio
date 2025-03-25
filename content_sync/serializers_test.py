"""Content sync serializer tests"""

import json
import re

import pytest
import yaml
from django.core.files.uploadedfile import SimpleUploadedFile
from moto import mock_s3

from content_sync.serializers import (
    BaseContentFileSerializer,
    ContentFileSerializerFactory,
    HugoMarkdownFileSerializer,
    HugoMenuYamlFileSerializer,
    JsonFileSerializer,
    YamlFileSerializer,
    deserialize_file_to_website_content,
    serialize_content_to_file,
)
from websites.constants import WEBSITE_CONFIG_ROOT_URL_PATH_KEY
from websites.factories import (
    WebsiteContentFactory,
    WebsiteFactory,
    WebsiteStarterFactory,
)
from websites.site_config_api import ConfigItem, SiteConfig

EXAMPLE_UUIDS = [
    "c5047db5-5d30-481f-878c-4fe79eebeeb1",
    "38223bd4-8eae-4a81-91c2-b36cac529d69",
]

EXAMPLE_HUGO_MARKDOWN = """---
title: Example File
content_type: page
uid: abcdefg
---
# My markdown
- abc
- def
"""

EXAMPLE_HUGO_MARKDOWN_WITH_FILE = """---
title: Example File
content_type: resource
uid: abcdefg
image: https://test.edu/courses/website_name-fall-2025/image.png
---
# My markdown
- abc
- def
"""

EXAMPLE_JSON = """{
  "tags": [
    "Design"
  ],
  "description": "**This** is the description",
  "title": "Content Title",
  "site_uid": "site_uid"
}
"""

EXAMPLE_YAML = """tags:
  - Design
description: '**This** is the description'
title: Content Title
"""

EXAMPLE_MENU_FILE_YAML = f"""mainmenu:
  - identifier: {EXAMPLE_UUIDS[0]}
    name: Page 1
    weight: 0
    pageRef: content/page-1.md
  - identifier: 'external-12345'
    name: Ext Link
    weight: 10
    url: http://example.com
  - identifier: {EXAMPLE_UUIDS[0]}
    name: Page 1 url and pageRef
    weight: 20
    pageRef: content/page-1.md
    url: content/page-1.md
"""


def get_example_menu_data():
    """Returns example menu data"""  # noqa: D401
    return [
        {"name": "Page 1", "weight": 0, "identifier": EXAMPLE_UUIDS[0]},
        {
            "name": "Ext Link",
            "weight": 10,
            "identifier": "external-12345",
            "url": "http://example.com",
        },
        {
            "name": "Page 1 url and pageRef",
            "weight": 20,
            "identifier": EXAMPLE_UUIDS[0],
        },
    ]


@mock_s3
@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("markdown", "exp_sections"),
    [["# Some markdown...\n- and\n- a\n- list", 2], [None, 1]],  # noqa: PT007
)
def test_hugo_file_serialize(settings, markdown, exp_sections):
    """HugoMarkdownFileSerializer.serialize should create the expected file contents"""
    settings.OCW_STUDIO_USE_S3 = True
    metadata = {"metadata1": "dummy value 1", "metadata2": "dummy value 2"}
    content = WebsiteContentFactory.create(
        text_id="abcdefg",
        title="Content Title",
        type="resource",
        markdown=markdown,
        metadata=metadata,
        file=SimpleUploadedFile("mysite/test.pdf", b"content"),
        website=WebsiteFactory.create(name="mysite", url_path="sites/mysite-fall-2025"),
    )
    site_config = SiteConfig(content.website.starter.config)

    file_content = HugoMarkdownFileSerializer(site_config).serialize(
        website_content=content
    )
    md_file_sections = [
        part
        for part in re.split(re.compile(r"^---\n", re.MULTILINE), file_content)
        # re.split returns a blank string as the first item here even though the file contents begin with the given
        # pattern.
        if part
    ]
    assert len(md_file_sections) == exp_sections
    front_matter = md_file_sections[0]
    front_matter_lines = list(filter(None, sorted(front_matter.split("\n"))))
    assert front_matter_lines == sorted(
        [
            f"title: {content.title}",
            f"content_type: {content.type}",
            f"uid: {content.text_id}",
        ]
        + [f"{k}: {v}" for k, v in metadata.items()]
    )
    assert (
        f"image: /media/{content.website.url_path}/{content.file.name.split('/')[-1]}"
        in front_matter_lines
    )
    if exp_sections > 1:
        assert md_file_sections[1] == markdown


@pytest.mark.django_db()
def test_hugo_file_deserialize(mocker):
    """HugoMarkdownFileSerializer.deserialize should create the expected content object from some file contents"""
    dest_directory, dest_filename = "path/to", "myfile"
    filepath = f"/{dest_directory}/{dest_filename}.md"
    patched_find_item = mocker.patch.object(
        SiteConfig,
        "find_item_by_name",
        return_value=ConfigItem(item={"folder": "different/path/to"}),
    )
    website = WebsiteFactory.create()
    site_config = SiteConfig(website.starter.config)
    serializer = HugoMarkdownFileSerializer(site_config)

    website_content = serializer.deserialize(
        website=website,
        filepath=filepath,
        file_contents=EXAMPLE_HUGO_MARKDOWN,
    )
    assert website_content.title == "Example File"
    assert website_content.type == "page"
    assert website_content.text_id == "abcdefg"
    assert website_content.markdown == "# My markdown\n- abc\n- def\n"
    assert website_content.is_page_content is True
    assert website_content.dirpath == dest_directory
    assert website_content.filename == dest_filename
    patched_find_item.assert_any_call("page")

    markdown_pos = EXAMPLE_HUGO_MARKDOWN.find(website_content.markdown)
    content_without_markdown = EXAMPLE_HUGO_MARKDOWN[0:markdown_pos]
    # deserialize() should update existing WebsiteContent records, and should be able to handle empty markdown.
    serializer.deserialize(
        website=website,
        filepath=filepath,
        file_contents=content_without_markdown,
    )
    website_content.refresh_from_db()
    assert website_content.markdown is None


@pytest.mark.django_db()
def test_hugo_menu_yaml_serialize(omnibus_config):
    """HugoMenuYamlFileSerializer.serialize should create the expected file contents"""
    nav_menu_config_item = omnibus_config.find_item_by_name("navmenu")
    assert nav_menu_config_item is not None
    # Create page object referred to in the menu data
    WebsiteContentFactory.create(
        text_id=EXAMPLE_UUIDS[0],
        is_page_content=True,
        dirpath="path/to",
        filename="myfile",
    )
    example_menu_data = get_example_menu_data()
    content = WebsiteContentFactory.build(
        is_page_content=False,
        type=nav_menu_config_item.name,
        metadata={"mainmenu": example_menu_data},
    )
    serialized_data = HugoMenuYamlFileSerializer(omnibus_config).serialize(content)
    parsed_serialized_data = yaml.load(serialized_data, Loader=yaml.SafeLoader)
    assert parsed_serialized_data == {
        "mainmenu": [
            {**example_menu_data[0], "pageRef": "/path/to/myfile"},
            example_menu_data[1],
            {**example_menu_data[2], "pageRef": "/path/to/myfile"},
        ]
    }


@pytest.mark.django_db()
def test_hugo_menu_yaml_deserialize(omnibus_config):
    """HugoMenuYamlFileSerializer.deserialize should create the expected content object from some file contents"""
    nav_menu_config_item = omnibus_config.find_item_by_name("navmenu")
    assert nav_menu_config_item is not None
    filepath = nav_menu_config_item.file_target
    website = WebsiteFactory.create()
    serializer = HugoMenuYamlFileSerializer(omnibus_config)
    website_content = serializer.deserialize(
        website=website,
        filepath=filepath,
        file_contents=EXAMPLE_MENU_FILE_YAML,
    )
    assert website_content.metadata == {
        "mainmenu": get_example_menu_data(),
    }


@mock_s3
@pytest.mark.django_db()
def test_hugo_file_deserialize_with_file(settings):
    """HugoMarkdownFileSerializer.deserialize should create the expected content object from some file contents"""
    settings.DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    website = WebsiteFactory.create(url_path="courses/website_name-fall-2025")
    website.starter.config[WEBSITE_CONFIG_ROOT_URL_PATH_KEY] = "courses"
    site_config = SiteConfig(website.starter.config)
    website_content = HugoMarkdownFileSerializer(site_config).deserialize(
        website=website,
        filepath="/test/file.md",
        file_contents=EXAMPLE_HUGO_MARKDOWN_WITH_FILE,
    )
    expected_path = f"courses/{website.name}/image.png"
    assert "image" not in website_content.metadata
    assert website_content.file == expected_path
    assert (
        website_content.file.url
        == f"https://s3.amazonaws.com/{settings.AWS_STORAGE_BUCKET_NAME}/{expected_path}"
    )


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("config_dirpath", "file_dirpath", "exp_content_dirpath"),
    [
        ["/config/path/to/", "config/path/to", "config/path/to"],  # noqa: PT007
        ["/config/path/to", "file/path/to", "file/path/to"],  # noqa: PT007
    ],
)
def test_hugo_file_deserialize_dirpath(
    mocker, config_dirpath, file_dirpath, exp_content_dirpath
):
    """
    HugoMarkdownFileSerializer.deserialize should create/update the WebsiteContent.dirpath value with a null value
    if the file exists at the path described in the site config
    """
    filepath = f"/{file_dirpath}/myfile.md"
    patched_find_item = mocker.patch.object(
        SiteConfig,
        "find_item_by_name",
        return_value=ConfigItem(item={"folder": config_dirpath}),
    )
    website = WebsiteFactory.create()
    site_config = SiteConfig(website.starter.config)
    website_content = HugoMarkdownFileSerializer(site_config).deserialize(
        website=website,
        filepath=filepath,
        file_contents=EXAMPLE_HUGO_MARKDOWN,
    )
    assert website_content.dirpath == exp_content_dirpath
    assert bool(website_content.file) is False
    patched_find_item.assert_any_call("page")


@pytest.mark.django_db()
@pytest.mark.parametrize("serializer_cls", [JsonFileSerializer, YamlFileSerializer])
def test_data_file_serialize(serializer_cls):
    """JsonFileSerializer and YamlFileSerializer.serialize should create the expected data file contents"""
    metadata = {"metadata1": "dummy value 1", "metadata2": "dummy value 2"}
    content = WebsiteContentFactory.create(
        text_id="abcdefg",
        title="Content Title",
        type="sometype",
        metadata=metadata,
    )
    site_config = SiteConfig(content.website.starter.config)
    file_content = serializer_cls(site_config).serialize(website_content=content)
    parsed_file_content = (
        json.loads(file_content)
        if serializer_cls == JsonFileSerializer
        else yaml.load(file_content, Loader=yaml.SafeLoader)
    )
    assert parsed_file_content == {**metadata, "title": "Content Title"}


@pytest.mark.django_db()
def test_metadata_file_serialize():
    """JsonFileSerializer should create the expected data file contents for sitemetadata files"""
    metadata = {"metadata1": "dummy value 1", "metadata2": "dummy value 2"}
    content = WebsiteContentFactory.create(
        text_id="abcdefg",
        title="Content Title",
        type="sitemetadata",
        metadata=metadata,
    )
    site_config = SiteConfig(content.website.starter.config)
    file_content = JsonFileSerializer(site_config).serialize(website_content=content)
    parsed_file_content = json.loads(file_content)

    assert parsed_file_content == {
        **metadata,
        "site_uid": str(content.website.uuid),
        "title": "Content Title",
    }


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("serializer_cls", "file_content"),
    [
        [JsonFileSerializer, EXAMPLE_JSON],  # noqa: PT007
        [YamlFileSerializer, EXAMPLE_YAML],  # noqa: PT007
    ],
)
def test_data_file_deserialize(serializer_cls, file_content):
    """
    JsonFileSerializer and YamlFileSerializer.deserialize should create the expected content object
    from some data file contents
    """
    website = WebsiteFactory.create()
    site_config = SiteConfig(website.starter.config)
    file_config_item = next(
        config_item
        for config_item in site_config.iter_items()
        if "file" in config_item.item
    )
    filepath = file_config_item.item["file"]
    website_content = serializer_cls(site_config).deserialize(
        website=website,
        filepath=filepath,
        file_contents=file_content,
    )
    assert website_content.title == "Content Title"
    assert website_content.type == file_config_item.item["name"]
    assert website_content.text_id == file_config_item.item["name"]
    assert website_content.is_page_content is False
    assert website_content.metadata == {
        "tags": ["Design"],
        "description": "**This** is the description",
    }


@pytest.mark.parametrize(
    ("filepath", "exp_serializer_cls"),
    [
        ["content/file.md", HugoMarkdownFileSerializer],  # noqa: PT007
        ["data/file.json", JsonFileSerializer],  # noqa: PT007
        ["data/file.yml", YamlFileSerializer],  # noqa: PT007
    ],
)
def test_factory_for_file(filepath, exp_serializer_cls):
    """ContentFileSerializerFactory.for_file should return the correct serializer class"""
    site_config = SiteConfig(WebsiteStarterFactory.build().config)
    assert isinstance(
        ContentFileSerializerFactory.for_file(
            site_config=site_config, filepath=filepath
        ),
        exp_serializer_cls,
    )


def test_factory_for_file_hugo_menu(omnibus_config):
    """
    ContentFileSerializerFactory.for_file should return the Hugo menu serializer class if the filepath is associated
    with a config item that has "menu" fields
    """
    nav_menu_config_item = omnibus_config.find_item_by_name("navmenu")
    assert nav_menu_config_item is not None
    assert isinstance(
        ContentFileSerializerFactory.for_file(
            site_config=omnibus_config, filepath=nav_menu_config_item.file_target
        ),
        HugoMenuYamlFileSerializer,
    )


def test_factory_for_file_invalid():
    """ContentFileSerializerFactory.for_file should raise when given an unsupported file type"""
    site_config = SiteConfig(WebsiteStarterFactory.build().config)
    with pytest.raises(ValueError):  # noqa: PT011
        assert ContentFileSerializerFactory.for_file(
            site_config=site_config, filepath="/path/to/myfile.tar.gz"
        )


def test_factory_for_content_hugo_markdown():
    """
    ContentFileSerializerFactory.for_content should return the Hugo markdown serializer if the content object
    is page content.
    """
    content = WebsiteContentFactory.build(is_page_content=True)
    site_config = SiteConfig(content.website.starter.config)
    assert isinstance(
        ContentFileSerializerFactory.for_content(site_config, content),
        HugoMarkdownFileSerializer,
    )


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("file_value", "exp_serializer_cls"),
    [
        ["data/file.json", JsonFileSerializer],  # noqa: PT007
        ["data/file.yml", YamlFileSerializer],  # noqa: PT007
    ],
)
def test_factory_for_content_data(file_value, exp_serializer_cls):
    """
    ContentFileSerializerFactory.for_content should return the correct data file serializer when given a content object
    that was created for a "file"-type config item.
    """
    content = WebsiteContentFactory.build(is_page_content=False, type="sometype")
    site_config = SiteConfig(content.website.starter.config)
    # Create a new "file"-type config item which will match our website content object
    raw_files_item = next(
        raw_config_item
        for raw_config_item in site_config.raw_data["collections"]
        if "files" in raw_config_item
    )
    new_files_item = raw_files_item.copy()
    new_files_item["name"] = "newfiles"
    new_files_item["files"] = [
        {**raw_files_item["files"][0].copy(), "name": content.type, "file": file_value}
    ]
    site_config.raw_data["collections"].append(new_files_item)

    assert isinstance(
        ContentFileSerializerFactory.for_content(site_config, content),
        exp_serializer_cls,
    )


def test_factory_for_content_hugo_menu(omnibus_config):
    """
    ContentFileSerializerFactory.for_content should return the Hugo menu serializer class if the content is
    associated with a config item that has "menu" fields
    """
    nav_menu_config_item = omnibus_config.find_item_by_name("navmenu")
    assert nav_menu_config_item is not None
    content = WebsiteContentFactory.build(
        is_page_content=False, type=nav_menu_config_item.name
    )
    assert isinstance(
        ContentFileSerializerFactory.for_content(
            site_config=omnibus_config, website_content=content
        ),
        HugoMenuYamlFileSerializer,
    )


def test_serialize_content_to_file(mocker):
    """serialize_content_to_file should pick the correct serializer class and serialize a website content object"""
    mock_serializer = mocker.MagicMock(spec=BaseContentFileSerializer)
    patched_serializer_factory = mocker.patch(
        "content_sync.serializers.ContentFileSerializerFactory", autospec=True
    )
    patched_serializer_factory.for_content.return_value = mock_serializer
    website_content = WebsiteContentFactory.build()
    site_config = SiteConfig(website_content.website.starter.config)
    serialized = serialize_content_to_file(
        site_config=site_config, website_content=website_content
    )

    patched_serializer_factory.for_content.assert_called_once_with(
        site_config, website_content
    )
    mock_serializer.serialize.assert_called_once_with(website_content=website_content)
    assert serialized == mock_serializer.serialize.return_value


def test_deserialize_file_to_website_content(mocker):
    """deserialize_file_to_website_content should pick the correct serializer class and deserialize file contents"""
    mock_serializer = mocker.MagicMock(spec=BaseContentFileSerializer)
    patched_serializer_factory = mocker.patch(
        "content_sync.serializers.ContentFileSerializerFactory", autospec=True
    )
    patched_serializer_factory.for_file.return_value = mock_serializer
    website = WebsiteFactory.build()
    site_config = SiteConfig(website.starter.config)
    filepath, file_contents = "/my/file.md", "..."
    deserialized = deserialize_file_to_website_content(
        website=website,
        site_config=site_config,
        filepath=filepath,
        file_contents=file_contents,
    )

    patched_serializer_factory.for_file.assert_called_once_with(site_config, filepath)
    mock_serializer.deserialize.assert_called_once_with(
        website=website,
        filepath=filepath,
        file_contents=file_contents,
    )
    assert deserialized == mock_serializer.deserialize.return_value
