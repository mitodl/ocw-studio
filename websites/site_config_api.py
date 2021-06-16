"""API functionality for working with site configs"""
from dataclasses import dataclass
from typing import Iterator, Optional

from django.utils.functional import cached_property

from main.utils import remove_trailing_slashes
from websites.constants import (
    WEBSITE_CONFIG_CONTENT_DIR_KEY,
    WEBSITE_CONFIG_DEFAULT_CONTENT_DIR,
)


@dataclass
class ConfigItem:
    """Utility class for describing an individual site config item"""

    item: dict
    parent_item: Optional[dict] = None
    path: str = ""

    @property
    def file_target(self) -> Optional[str]:
        """
        Returns the destination folder/directory if this is a folder-type config item, or the full destination filepath
        if this is a file-type config item.
        """
        return self.item.get("folder") or self.item.get("file")

    def has_file_target(self) -> bool:
        """Returns True if this config item has a file/folder target"""
        return self.file_target is not None

    @property
    def name(self) -> str:
        """Helper property to return the 'name' value"""
        return self.item["name"]

    @property
    def fields(self) -> list:
        """Helper property to return the 'fields' value"""
        return self.item.get("fields", [])

    def is_folder_item(self) -> bool:
        """Returns True if this config item has a folder target"""
        return "folder" in self.item

    def is_file_item(self) -> bool:
        """Returns True if this config item has a file target"""
        return "file" in self.item


class SiteConfig:
    """Utility class for parsing and introspecting site configs"""

    def __init__(self, raw_data):
        self.raw_data = raw_data

    @cached_property
    def content_dir(self) -> str:
        """
        Returns the content directory described in the site config, or the default if that directory isn't included
        """
        return (
            self.raw_data.get(WEBSITE_CONFIG_CONTENT_DIR_KEY)
            or WEBSITE_CONFIG_DEFAULT_CONTENT_DIR
        )

    def iter_items(self) -> Iterator[ConfigItem]:
        """Yields all config items for which users can enter data"""
        collections = self.raw_data.get("collections")
        for i, collection_item in enumerate(collections):
            path = f"collections.{i}"
            yield ConfigItem(item=collection_item, parent_item=None, path=path)
            if "files" in collection_item:
                for j, inner_collection_item in enumerate(collection_item["files"]):
                    yield ConfigItem(
                        item=inner_collection_item,
                        parent_item=collection_item,
                        path=f"{path}.files.{j}",
                    )

    def find_item_by_name(self, name: str) -> Optional[ConfigItem]:
        """Finds a config item in the site config with a matching 'name' value"""
        for config_item in self.iter_items():
            if config_item.item.get("name") == name:
                return config_item
        return None

    def find_item_by_filepath(self, filepath: str) -> Optional[ConfigItem]:
        """Finds a config item in the site config with a matching 'file' value"""
        filepath = remove_trailing_slashes(filepath)
        for config_item in self.iter_items():
            if (
                config_item.is_file_item()
                and remove_trailing_slashes(config_item.file_target) == filepath
            ):
                return config_item
        return None

    def is_page_content(self, config_item: ConfigItem) -> bool:
        """
        Returns True if the given config item describes page content, as opposed to data/configuration
        """
        file_target = config_item.file_target
        return file_target is not None and (
            file_target == self.content_dir
            or file_target.startswith(f"{self.content_dir}/")
        )
