"""Serialization/deserialization logic for transforming database content into file content and vice versa"""  # noqa: E501

import abc
import json
import re
from urllib.parse import urlparse

import yaml
from mitol.common.utils import dict_without_keys

from content_sync.utils import get_destination_url
from main.utils import (
    get_dirpath_and_filename,
    get_file_extension,
    is_valid_uuid,
    remove_trailing_slashes,
)
from websites.constants import CONTENT_MENU_FIELD, CONTENT_TYPE_METADATA
from websites.models import Website, WebsiteContent
from websites.site_config_api import ConfigItem, SiteConfig


class BaseContentFileSerializer(abc.ABC):
    """Base class for a serializer that can serialize WebsiteContent objects into file contents and vice versa"""  # noqa: E501

    def __init__(self, site_config: SiteConfig):
        self.site_config = site_config

    @abc.abstractmethod
    def serialize(self, website_content: WebsiteContent) -> str:
        """Serializes WebsiteContent data into file contents"""  # noqa: D401

    @abc.abstractmethod
    def deserialize(
        self, website: Website, filepath: str, file_contents: str
    ) -> WebsiteContent:
        """Deserializes file contents and upserts those contents as a WebsiteContent object"""  # noqa: E501

    def deserialize_data_file(
        self, website: Website, filepath: str, parsed_file_data: dict
    ) -> WebsiteContent:
        """Helper method to deserialize simple data file contents"""  # noqa: D401
        title = parsed_file_data.get("title")
        config_item = self.site_config.find_item_by_filepath(filepath)
        text_id = config_item.name
        base_defaults = {
            "metadata": dict_without_keys(parsed_file_data, "title"),
            "text_id": text_id,
            # "file"-type items are singletons, and we use the same value for text_id and type  # noqa: E501
            "type": text_id,
            "is_page_content": False,
            **({"title": title} if title is not None else {}),
        }
        content, _ = WebsiteContent.objects.update_or_create(
            website=website, text_id=text_id, defaults=base_defaults
        )
        return content

    @staticmethod
    def serialize_contents(metadata: dict, title: str | None) -> dict:
        """Standard serializer function for website content data"""  # noqa: D401
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
            "content_type": website_content.type,
        }
        # NOTE: yaml.dump adds a newline to the end of its output by default
        return f"---\n{yaml.dump(front_matter)}---\n{website_content.markdown or ''}"

    def deserialize(  # pylint:disable=too-many-locals
        self, website: Website, filepath: str, file_contents: str
    ) -> WebsiteContent:
        md_file_sections = [
            part
            for part in re.split(re.compile(r"^---\n", re.MULTILINE), file_contents)
            # re.split returns a blank string as the first item here even though the file contents begin with the given  # noqa: E501
            # pattern.
            if part
        ]
        if not 1 <= len(md_file_sections) <= 2:  # noqa: PLR2004
            msg = f"Incorrectly formatted Markdown file ({filepath})."
            raise ValueError(msg)
        front_matter_data = yaml.load(md_file_sections[0], Loader=yaml.SafeLoader)
        markdown = (
            md_file_sections[1] if len(md_file_sections) == 2 else None  # noqa: PLR2004
        )
        text_id = front_matter_data.get("uid", None)
        content_type = front_matter_data.get("content_type")
        dirpath, filename = get_dirpath_and_filename(
            filepath, expect_file_extension=True
        )
        omitted_keys = ["uid", "title", "type"]
        file_url = None
        config_item = self.site_config.find_item_by_name(content_type)
        if config_item is None:
            msg = f"Could not find matching config item for this file ({filepath}, type: {content_type})"  # noqa: E501
            raise ValueError(msg)
        content_config = self.site_config.find_item_by_name(content_type)
        if content_config:
            file_field = self.site_config.find_file_field(content_config)
            if file_field:
                omitted_keys.append(file_field["name"])
                file_url = front_matter_data.get(file_field["name"], None)
                if file_url is not None:
                    s3_path = website.s3_path
                    url_path = website.url_path
                    file_url = urlparse(file_url).path.lstrip("/")
                    if url_path and s3_path != url_path:
                        file_url = file_url.replace(url_path, s3_path, 1)

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
        metadata = website_content.metadata
        if website_content.type == CONTENT_TYPE_METADATA:
            metadata["site_uid"] = str(website_content.website.uuid)
            metadata["site_short_id"] = str(website_content.website.short_id)

        return json.dumps(
            self.serialize_contents(metadata, website_content.title),
            indent=2,
        )

    def deserialize(
        self, website: Website, filepath: str, file_contents: str
    ) -> WebsiteContent:
        parsed_file_data = json.loads(file_contents)
        return self.deserialize_data_file(
            website=website,
            filepath=filepath,
            parsed_file_data=dict_without_keys(parsed_file_data, "site_uid"),
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
        parsed_file_data = yaml.load(file_contents, Loader=yaml.SafeLoader)
        return self.deserialize_data_file(
            website=website,
            filepath=filepath,
            parsed_file_data=parsed_file_data,
        )


def _has_menu_fields(config_item: ConfigItem) -> bool:
    """Returns True if the config item has any fields with the 'menu' widget"""  # noqa: D401
    return any(
        field for field in config_item.fields if field["widget"] == CONTENT_MENU_FIELD
    )


def _get_uuid_content_map(hugo_menu_data: dict) -> dict[str, WebsiteContent]:
    """Returns a mapping of UUIDs to the WebsiteContent records with those ids"""  # noqa: D401
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
) -> dict:
    """
    Adds 'pageRef' property to links in menu data.

    Returns the dict of all values that will be serialized to the target file, including the transformed
    "menu" fields.
    """  # noqa: D401, E501
    config_item = site_config.find_item_by_name(website_content.type)
    menu_fields = {
        field["name"]
        for field in config_item.fields
        if field.get("widget") == CONTENT_MENU_FIELD
    }
    transformed_menu_fields = {}
    for field_name, field_data in website_content.metadata.items():
        if field_name not in menu_fields:
            continue
        uuid_content_map = _get_uuid_content_map(field_data)
        result_menu_items = []
        for menu_item in field_data:
            updated_menu_item = menu_item
            # Add/update the 'pageRef' value if this is a link
            if menu_item["identifier"] in uuid_content_map:
                menu_item_content = uuid_content_map[menu_item["identifier"]]
                updated_menu_item["pageRef"] = get_destination_url(
                    menu_item_content, site_config
                )
                # deletes 'url' property, if also present in legacy data
                if "url" in updated_menu_item:
                    del updated_menu_item["url"]
            result_menu_items.append(updated_menu_item)
        transformed_menu_fields[field_name] = result_menu_items
    return {**website_content.metadata, **transformed_menu_fields}


def _untransform_hugo_menu_data(
    data: dict, filepath: str, site_config: SiteConfig
) -> dict:
    """
    Removes 'pageRef' property from internal links in serialized menu data.

    Returns the dict of all values that will be deserialized to website content, including the transformed
    "menu" fields.
    """  # noqa: D401, E501
    config_item = site_config.find_item_by_filepath(filepath)
    menu_fields = {
        field["name"]
        for field in config_item.fields
        if field.get("widget") == CONTENT_MENU_FIELD
    }
    transformed_menu_fields = {}
    for field_name, field_data in data.items():
        if field_name not in menu_fields:
            continue
        result_menu_items = []
        for menu_item in field_data:
            updated_menu_item = menu_item.copy()
            if (
                is_valid_uuid(updated_menu_item["identifier"])
                and "pageRef" in updated_menu_item
            ):
                del updated_menu_item["pageRef"]
                # deletes 'url' property, if also present in legacy data
                if "url" in updated_menu_item:
                    del updated_menu_item["url"]
            result_menu_items.append(updated_menu_item)
        transformed_menu_fields[field_name] = result_menu_items
    return {**data, **transformed_menu_fields}


class HugoMenuYamlFileSerializer(BaseContentFileSerializer):
    """
    HACK: Hugo-specific logic for properly transforming data if the "menu" widget is used

    Serializer/deserializer class for Hugo menu files
    """  # noqa: E501

    def serialize(self, website_content: WebsiteContent) -> str:
        return yaml.dump(
            self.serialize_contents(
                metadata=_transform_hugo_menu_data(website_content, self.site_config),
                title=None,
            ),
            Dumper=yaml.Dumper,
        )

    def deserialize(
        self, website: Website, filepath: str, file_contents: str
    ) -> WebsiteContent:
        parsed_file_data = yaml.load(file_contents, Loader=yaml.SafeLoader)
        return self.deserialize_data_file(
            website=website,
            filepath=filepath,
            parsed_file_data=_untransform_hugo_menu_data(
                data=parsed_file_data,
                filepath=filepath,
                site_config=self.site_config,
            ),
        )


class ContentFileSerializerFactory:
    """Provides methods which return the appropriate file serializer/deserializer"""

    @staticmethod
    def for_file(site_config: SiteConfig, filepath: str) -> BaseContentFileSerializer:
        """
        Given the path of a file in a storage backend, returns a serializer object of the correct type for
        deserializing the file as a WebsiteContent object.
        """  # noqa: E501
        file_ext = get_file_extension(filepath)
        if file_ext == "md":
            cls = HugoMarkdownFileSerializer
        elif file_ext == "json":
            cls = JsonFileSerializer
        elif file_ext in {"yml", "yaml"}:
            # HACK: Hugo-specific logic for properly transforming data if the "menu" widget is used  # noqa: E501, FIX004
            config_item = site_config.find_item_by_filepath(filepath)
            if config_item is not None and _has_menu_fields(config_item):
                cls = HugoMenuYamlFileSerializer
            else:
                cls = YamlFileSerializer
        else:
            msg = f"Unrecognized file type. Cannot deserialize ({filepath})."
            raise ValueError(msg)
        return cls(site_config=site_config)

    @staticmethod
    def for_content(
        site_config: SiteConfig, website_content: WebsiteContent
    ) -> BaseContentFileSerializer:
        """
        Given a WebsiteContent object and site config, returns a serializer object of the correct type for
        serializing the WebsiteContent object into file contents.
        """  # noqa: E501
        if website_content.is_page_content:
            return HugoMarkdownFileSerializer(site_config=site_config)
        config_item = site_config.find_item_by_name(website_content.type)
        destination_filepath = config_item.file_target
        if not destination_filepath:
            msg = f"WebsiteContent object is not page content, but has no 'file' destination in config ({website_content.text_id})."  # noqa: E501
            raise ValueError(msg)
        file_ext = get_file_extension(destination_filepath)
        if file_ext == "json":
            cls = JsonFileSerializer
        elif file_ext in {"yml", "yaml"}:
            # HACK: Hugo-specific logic for properly transforming data if the "menu" widget is used  # noqa: E501, FIX004
            if _has_menu_fields(config_item):
                cls = HugoMenuYamlFileSerializer
            else:
                cls = YamlFileSerializer
        else:
            msg = f"Website content cannot be serialized to a file ({website_content.text_id})."  # noqa: E501
            raise ValueError(msg)
        return cls(site_config=site_config)


def serialize_content_to_file(
    site_config: SiteConfig, website_content: WebsiteContent
) -> str:
    """
    Chooses the correct serializer for the given website content object, then serializes the WebsiteContent
    object into file contents.
    """  # noqa: E501
    serializer = ContentFileSerializerFactory.for_content(site_config, website_content)
    return serializer.serialize(website_content=website_content)


def deserialize_file_to_website_content(
    site_config: SiteConfig, website: Website, filepath: str, file_contents: str
) -> WebsiteContent:
    """
    Given a WebsiteContent object and site config, chooses the correct serializer, then serializes the WebsiteContent
    object into file contents.
    """  # noqa: E501
    serializer = ContentFileSerializerFactory.for_file(site_config, filepath)
    return serializer.deserialize(
        website=website,
        filepath=filepath,
        file_contents=file_contents,
    )
