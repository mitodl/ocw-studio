"""Serialization/deserialization logic for transforming database content into file content and vice versa"""
import abc
import json
import re
from typing import Type

import yaml
from mitol.common.utils import dict_without_keys

from main.utils import (
    get_dirpath_and_filename,
    get_file_extension,
    remove_trailing_slashes,
)
from websites.models import Website, WebsiteContent
from websites.site_config_api import SiteConfig


class BaseContentFileSerializer(abc.ABC):
    """Base class for a serializer that can serialize WebsiteContent objects into file contents and vice versa"""

    @staticmethod
    @abc.abstractmethod
    def serialize(website_content: WebsiteContent) -> str:
        """Serializes WebsiteContent data into file contents"""
        ...

    @staticmethod
    @abc.abstractmethod
    def deserialize(
        website: Website, site_config: SiteConfig, filepath: str, file_contents: str
    ) -> WebsiteContent:
        """Deserializes file contents and upserts those contents as a WebsiteContent object"""
        ...

    @staticmethod
    def deserialize_data_file(
        website: Website, site_config: SiteConfig, filepath: str, parsed_file_data: dict
    ) -> WebsiteContent:
        """Helper method to deserialize simple data file contents"""
        title = parsed_file_data.get("title")
        config_item = site_config.find_item_by_filepath(filepath)
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


class HugoMarkdownFileSerializer(BaseContentFileSerializer):
    """Serializer/deserializer class for Hugo Markdown content and files"""

    @staticmethod
    def serialize(website_content: WebsiteContent) -> str:
        front_matter = {
            **(website_content.full_metadata or {}),
            "uid": website_content.text_id,
            "title": website_content.title,
            "type": website_content.type,
        }
        # NOTE: yaml.dump adds a newline to the end of its output by default
        return f"---\n{yaml.dump(front_matter)}---\n{website_content.markdown or ''}"

    @staticmethod
    def deserialize(  # pylint:disable=too-many-locals
        website: Website, site_config: SiteConfig, filepath: str, file_contents: str
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
        config_item = site_config.find_item_by_name(content_type)
        if config_item is None:
            raise ValueError(
                f"Could not find matching config item for this file ({filepath}, type: {content_type})"
            )
        content_config = site_config.find_item_by_name(content_type)
        if content_config:
            file_field = site_config.find_file_field(content_config)
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

    @staticmethod
    def serialize(website_content: WebsiteContent) -> str:
        return json.dumps(
            {
                **website_content.metadata,
                **(
                    {"title": website_content.title}
                    if website_content.title is not None
                    else {}
                ),
            },
            indent=2,
        )

    @staticmethod
    def deserialize(
        website: Website, site_config: SiteConfig, filepath: str, file_contents: str
    ) -> WebsiteContent:
        parsed_file_data = json.loads(file_contents)
        return BaseContentFileSerializer.deserialize_data_file(
            website=website,
            site_config=site_config,
            filepath=filepath,
            parsed_file_data=parsed_file_data,
        )


class YamlFileSerializer(BaseContentFileSerializer):
    """Serializer/deserializer class for pure YAML content and files"""

    @staticmethod
    def serialize(website_content: WebsiteContent) -> str:
        return yaml.dump(
            {
                **website_content.metadata,
                **(
                    {"title": website_content.title}
                    if website_content.title is not None
                    else {}
                ),
            },
            Dumper=yaml.Dumper,
        )

    @staticmethod
    def deserialize(
        website: Website, site_config: SiteConfig, filepath: str, file_contents: str
    ) -> WebsiteContent:
        parsed_file_data = yaml.load(file_contents, Loader=yaml.Loader)
        return BaseContentFileSerializer.deserialize_data_file(
            website=website,
            site_config=site_config,
            filepath=filepath,
            parsed_file_data=parsed_file_data,
        )


class ContentFileSerializerFactory:
    """Provides methods which return the appropriate file serializer/deserializer"""

    @staticmethod
    def for_file(filepath: str) -> Type[BaseContentFileSerializer]:
        """
        Given the path of a file in a storage backend, returns the a serializer object of the correct type for
        deserializing the file as a WebsiteContent object.
        """
        file_ext = get_file_extension(filepath)
        if file_ext == "md":
            return HugoMarkdownFileSerializer
        if file_ext == "json":
            return JsonFileSerializer
        if file_ext == "yml":
            return YamlFileSerializer
        raise ValueError(f"Unrecognized file type. Cannot deserialize ({filepath}).")

    @staticmethod
    def for_content(
        site_config: SiteConfig, website_content: WebsiteContent
    ) -> Type[BaseContentFileSerializer]:
        """
        Given a WebsiteContent object and site config, returns a serializer object of the correct type for
        serializing the WebsiteContent object into file contents.
        """
        if website_content.is_page_content:
            return HugoMarkdownFileSerializer
        config_item = site_config.find_item_by_name(website_content.type)
        destination_filepath = config_item.file_target
        if not destination_filepath:
            raise ValueError(
                f"WebsiteContent object is not page content, but has no 'file' destination in config ({website_content.text_id})."
            )
        file_ext = get_file_extension(destination_filepath)
        if file_ext == "json":
            return JsonFileSerializer
        if file_ext == "yml":
            return YamlFileSerializer
        raise ValueError(
            f"Website content cannot be serialized to a file ({website_content.text_id})."
        )


def serialize_content_to_file(
    site_config: SiteConfig, website_content: WebsiteContent
) -> str:
    """
    Chooses the correct serializer for the given website content object, then serializes the WebsiteContent
    object into file contents.
    """
    serializer_cls = ContentFileSerializerFactory.for_content(
        site_config, website_content
    )
    return serializer_cls.serialize(website_content=website_content)


def deserialize_file_to_website_content(
    site_config: SiteConfig, website: Website, filepath: str, file_contents: str
) -> WebsiteContent:
    """
    Given a WebsiteContent object and site config, chooses the correct serializer, then serializes the WebsiteContent
    object into file contents.
    """
    serializer_cls = ContentFileSerializerFactory.for_file(filepath)
    return serializer_cls.deserialize(
        website=website,
        site_config=site_config,
        filepath=filepath,
        file_contents=file_contents,
    )
