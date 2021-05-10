"""API functionality for working with site configs"""

from typing import Iterator, NamedTuple, Optional

from main.utils import remove_trailing_slashes
from websites.constants import (
    WEBSITE_CONFIG_CONTENT_DIR_KEY,
    WEBSITE_CONFIG_DEFAULT_CONTENT_DIR,
)


def get_file_target(raw_config_item):
    """
    Returns the target (file or folder) of the config item (or None if the config item has no target)

    Args:
        raw_config_item (dict): A config item

    Returns:
        str or None: The destination file/folder of the config item
    """
    return raw_config_item.get("folder") or raw_config_item.get("file")


def has_file_target(raw_config_item):
    """
    Returns True if the config item has a file/folder target
    Args:
        raw_config_item (dict): A config item

    Returns:
        bool: True if the config item has a file/folder target
    """
    return get_file_target(raw_config_item) is not None


class ConfigItem(NamedTuple):
    """Utility class for describing a site config item"""

    item: dict
    parent_item: Optional[dict]
    path: str


class SiteConfig:
    """Utility class for parsing and introspecting site configs"""

    def __init__(self, raw_data):
        self.raw_data = raw_data

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

    def find_item_by_name(self, name: str) -> Optional[dict]:
        """Finds a config item in the site config with a matching 'name' value"""
        for config_item in self.iter_items():
            if config_item.item.get("name") == name:
                return config_item.item
        return None

    def find_item_by_filepath(self, filepath: str) -> Optional[dict]:
        """Finds a config item in the site config with a matching 'file' value"""
        filepath = remove_trailing_slashes(filepath)
        for config_item in self.iter_items():
            if (
                "file" in config_item.item
                and remove_trailing_slashes(config_item.item.get("file")) == filepath
            ):
                return config_item.item
        return None

    def is_page_content(self, raw_config_item: dict) -> bool:
        """
        Returns True if the given config item describes page content, as opposed to data/configuration
        """
        file_target = get_file_target(raw_config_item)
        content_dir = self.raw_data.get(
            WEBSITE_CONFIG_CONTENT_DIR_KEY, WEBSITE_CONFIG_DEFAULT_CONTENT_DIR
        )
        return file_target == content_dir or file_target.startswith(f"{content_dir}/")
