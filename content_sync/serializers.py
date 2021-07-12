"""Serialization/deserialization logic for transforming database content into file content and vice versa"""
import abc
import json
import re
from typing import Dict, Optional, Tuple

import yaml
from mitol.common.utils import dict_without_keys

from content_sync.utils import get_destination_filepath
from main.utils import (
    get_dirpath_and_filename,
    get_file_extension,
    is_valid_uuid,
    remove_trailing_slashes,
)
from websites.constants import CONTENT_MENU_FIELD
from websites.models import Website, WebsiteContent
from websites.site_config_api import ConfigItem, SiteConfig


class BaseContentFileSerializer(abc.ABC):
    """Base class for a serializer that can serialize WebsiteContent objects into file contents and vice versa"""

    def __init__(self, site_config: SiteConfig):
        self.site_config = site_config

    @abc.abstractmethod
    def serialize(self, website_content: WebsiteContent) -> str:
        """Serializes WebsiteContent data into file contents"""
        ...

    @abc.abstractmethod
    def deserialize(
        self, website: Website, filepath: str, file_contents: str
    ) -> WebsiteContent:
        """Deserializes file contents and upserts those contents as a WebsiteContent object"""
        ...

    def deserialize_data_file(
        self, website: Website, filepath: str, parsed_file_data: dict
    ) -> WebsiteContent:
        """Helper method to deserialize simple data file contents"""
        title = parsed_file_data.get("title")
        config_item = self.site_config.find_item_by_filepath(filepath)
        text_id = config_item.name
        base_defaults = {
            "metadata": dict_without_keys(parsed_file_data, "title"),
            "text_id": text_id,
            # "file"-type items are singletons, and we use the same value for text_id and type
            "type": text_id,
            "is_page_content": False,
            **({"title": title} if title is not None else {}),
        }
        content, _ = WebsiteContent.objects.update_or_create(
            website=website, text_id=text_id, defaults=base_defaults
        )
        return content

    @staticmethod
    def serialize_contents(metadata: dict, title: Optional[str]) -> dict:
        """Standard serializer function for website content data"""
        return {
            **metadata,
            **({"title": title} if title is not None else {}),
        }


class HugoMarkdownFileSerializer(BaseContentFileSerializer):
    """Serializer/deserializer class for Hugo Markdown content and files"""

    def serialize(self, website_content: WebsiteContent) -> str:
        front_matter = {
            **(website_content.full_metadata or {}),
            "uid": website_content.text_id,
            "title": website_content.title,
            "type": website_content.type,
        }
        # NOTE: yaml.dump adds a newline to the end of its output by default
        return f"---\n{yaml.dump(front_matter)}---\n{website_content.markdown or ''}"

    def deserialize(  # pylint:disable=too-many-locals
        self, website: Website, filepath: str, file_contents: str
    ) -> WebsiteContent:
        md_file_sections = [
            part
            for part in re.split(re.compile(r"^---\n", re.MULTILINE), file_contents)
            # re.split returns a blank string as the first item here even though the file contents begin with the given
            # pattern.
            if part
        ]
        if not 1 <= len(md_file_sections) <= 2:
            raise ValueError(f"Incorrectly formatted Markdown file ({filepath}).")
        front_matter_data = yaml.load(md_file_sections[0], Loader=yaml.Loader)
        markdown = md_file_sections[1] if len(md_file_sections) == 2 else None
        text_id = front_matter_data.get("uid", None)
        content_type = front_matter_data.get("type")
        dirpath, filename = get_dirpath_and_filename(
            filepath, expect_file_extension=True
        )
        omitted_keys = ["uid", "title", "type"]
        file_url = None
        config_item = self.site_config.find_item_by_name(content_type)
        if config_item is None:
            raise ValueError(
                f"Could not find matching config item for this file ({filepath}, type: {content_type})"
            )
        content_config = self.site_config.find_item_by_name(content_type)
        if content_config:
            file_field = self.site_config.find_file_field(content_config)
            if file_field:
                omitted_keys.append(file_field["name"])
                file_url = front_matter_data.get(file_field["name"], None)

        base_defaults = {
            "metadata": dict_without_keys(front_matter_data, *omitted_keys),
            "markdown": markdown,
            "text_id": text_id,
            "title": front_matter_data.get("title"),
            "type": content_type,
            "dirpath": remove_trailing_slashes(dirpath),
            "filename": filename,
            "is_page_content": True,
            "file": file_url,
        }
        content, _ = WebsiteContent.objects.update_or_create(
            website=website, text_id=text_id, defaults=base_defaults
        )
        return content


class JsonFileSerializer(BaseContentFileSerializer):
    """Serializer/deserializer class for pure JSON content and files"""

    def serialize(self, website_content: WebsiteContent) -> str:
        return json.dumps(
            self.serialize_contents(website_content.metadata, website_content.title),
            indent=2,
        )

    def deserialize(
        self, website: Website, filepath: str, file_contents: str
    ) -> WebsiteContent:
        parsed_file_data = json.loads(file_contents)
        return self.deserialize_data_file(
            website=website,
            filepath=filepath,
            parsed_file_data=parsed_file_data,
        )


class YamlFileSerializer(BaseContentFileSerializer):
    """Serializer/deserializer class for pure YAML content and files"""

    def serialize(self, website_content: WebsiteContent) -> str:
        return yaml.dump(
            self.serialize_contents(website_content.metadata, website_content.title),
            Dumper=yaml.Dumper,
        )

    def deserialize(
        self, website: Website, filepath: str, file_contents: str
    ) -> WebsiteContent:
        parsed_file_data = yaml.load(file_contents, Loader=yaml.Loader)
        return self.deserialize_data_file(
            website=website,
            filepath=filepath,
            parsed_file_data=parsed_file_data,
        )


def _has_menu_fields(config_item: ConfigItem) -> bool:
    """Returns True if the config item has any fields with the 'menu' widget"""
    return any(
        [field for field in config_item.fields if field["widget"] == CONTENT_MENU_FIELD]
    )


def _get_uuid_content_map(hugo_menu_data: dict) -> Dict[str, WebsiteContent]:
    """Returns a mapping of UUIDs to the WebsiteContent records with those ids"""
    content_uuids = [
        menu_item["identifier"]
        for menu_item in hugo_menu_data
        if is_valid_uuid(menu_item["identifier"])
    ]
    return {
        website_content.text_id: website_content
        for website_content in WebsiteContent.objects.filter(text_id__in=content_uuids)
    }


def _transform_hugo_menu_data(
    website_content: WebsiteContent, site_config: SiteConfig
) -> Tuple[dict, dict]:
    """
    Adds 'url' property to internal links in menu data, and namespaces the menu data under "menu" in the
    resulting dict (ref: https://gohugo.io/content-management/menus/#add-non-content-entries-to-a-menu)

    Returns two dicts: the metadata with "menu" widget fields removed, and the transformed menu data namespaced
        under "menu"
    """
    config_item = site_config.find_item_by_name(website_content.type)
    menu_fields = {
        field["name"]
        for field in config_item.fields
        if field.get("widget") == CONTENT_MENU_FIELD
    }
    result_menu = {}
    for field_name in website_content.metadata.keys():
        if field_name not in menu_fields:
            continue
        menu_data = website_content.metadata[field_name]
        uuid_content_map = _get_uuid_content_map(menu_data)
        result_menu_items = []
        for menu_item in menu_data:
            updated_menu_item = menu_item
            # Add/update the 'url' value if this is an internal link
            if menu_item["identifier"] in uuid_content_map:
                menu_item_content = uuid_content_map[menu_item["identifier"]]
                updated_menu_item["url"] = get_destination_filepath(
                    menu_item_content, site_config
                )
            result_menu_items.append(updated_menu_item)
        result_menu[field_name] = result_menu_items
    return (
        dict_without_keys(website_content.metadata, *menu_fields),
        ({CONTENT_MENU_FIELD: result_menu} if result_menu else {}),
    )


class HugoMenuYamlFileSerializer(BaseContentFileSerializer):
    """
    HACK: Hugo-specific logic for properly transforming data if the "menu" widget is used

    Serializer/deserializer class for Hugo menu files
    """

    def serialize(self, website_content: WebsiteContent) -> str:
        non_menu_metadata, menu_data = _transform_hugo_menu_data(
            website_content, self.site_config
        )
        return yaml.dump(
            self.serialize_contents(
                metadata={**menu_data, **non_menu_metadata}, title=website_content.title
            ),
            Dumper=yaml.Dumper,
        )

    def deserialize(
        self, website: Website, filepath: str, file_contents: str
    ) -> WebsiteContent:
        parsed_file_data = yaml.load(file_contents, Loader=yaml.Loader)
        if CONTENT_MENU_FIELD in parsed_file_data:
            parsed_file_data = {
                **parsed_file_data[CONTENT_MENU_FIELD],
                **dict_without_keys(parsed_file_data, CONTENT_MENU_FIELD),
            }
        return self.deserialize_data_file(
            website=website,
            filepath=filepath,
            parsed_file_data=parsed_file_data,
        )


class ContentFileSerializerFactory:
    """Provides methods which return the appropriate file serializer/deserializer"""

    @staticmethod
    def for_file(site_config: SiteConfig, filepath: str) -> BaseContentFileSerializer:
        """
        Given the path of a file in a storage backend, returns the a serializer object of the correct type for
        deserializing the file as a WebsiteContent object.
        """
        file_ext = get_file_extension(filepath)
        if file_ext == "md":
            cls = HugoMarkdownFileSerializer
        elif file_ext == "json":
            cls = JsonFileSerializer
        elif file_ext == "yml":
            # HACK: Hugo-specific logic for properly transforming data if the "menu" widget is used
            config_item = site_config.find_item_by_filepath(filepath)
            if config_item is not None and _has_menu_fields(config_item):
                cls = HugoMenuYamlFileSerializer
            else:
                cls = YamlFileSerializer
        else:
            raise ValueError(
                f"Unrecognized file type. Cannot deserialize ({filepath})."
            )
        return cls(site_config=site_config)

    @staticmethod
    def for_content(
        site_config: SiteConfig, website_content: WebsiteContent
    ) -> BaseContentFileSerializer:
        """
        Given a WebsiteContent object and site config, returns a serializer object of the correct type for
        serializing the WebsiteContent object into file contents.
        """
        if website_content.is_page_content:
            return HugoMarkdownFileSerializer(site_config=site_config)
        config_item = site_config.find_item_by_name(website_content.type)
        destination_filepath = config_item.file_target
        if not destination_filepath:
            raise ValueError(
                f"WebsiteContent object is not page content, but has no 'file' destination in config ({website_content.text_id})."
            )
        file_ext = get_file_extension(destination_filepath)
        if file_ext == "json":
            cls = JsonFileSerializer
        elif file_ext == "yml":
            # HACK: Hugo-specific logic for properly transforming data if the "menu" widget is used
            if _has_menu_fields(config_item):
                cls = HugoMenuYamlFileSerializer
            else:
                cls = YamlFileSerializer
        else:
            raise ValueError(
                f"Website content cannot be serialized to a file ({website_content.text_id})."
            )
        return cls(site_config=site_config)


def serialize_content_to_file(
    site_config: SiteConfig, website_content: WebsiteContent
) -> str:
    """
    Chooses the correct serializer for the given website content object, then serializes the WebsiteContent
    object into file contents.
    """
    serializer = ContentFileSerializerFactory.for_content(site_config, website_content)
    return serializer.serialize(website_content=website_content)


def deserialize_file_to_website_content(
    site_config: SiteConfig, website: Website, filepath: str, file_contents: str
) -> WebsiteContent:
    """
    Given a WebsiteContent object and site config, chooses the correct serializer, then serializes the WebsiteContent
    object into file contents.
    """
    serializer = ContentFileSerializerFactory.for_file(site_config, filepath)
    return serializer.deserialize(
        website=website,
        filepath=filepath,
        file_contents=file_contents,
    )
