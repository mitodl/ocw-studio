"""API functionality for working with site configs"""

from typing import NamedTuple, Optional

from websites.constants import (
    WEBSITE_CONFIG_CONTENT_DIR_KEY,
    WEBSITE_CONFIG_DEFAULT_CONTENT_DIR,
)


class ConfigItem(NamedTuple):
    """Utility class for describing a site config item"""

    item: dict
    parent_item: Optional[dict]
    path: str


def config_item_iter(site_config_data):
    """
    Yields information about every individual config item in a site config

    Args:
        site_config_data (dict): A parsed site config

    Yields:
        ConfigItem: An object containing an individual config item, its parent config item (if one exists), and a
            string describing the item's path
    """
    collections = site_config_data.get("collections")
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


def find_config_item(site_config_data, name):
    """
    Finds a config item in a site config by the given name

    Args:
        site_config_data (dict): The site config to search
        name (str): The name of the config item to find

    Returns:
        dict or None: The config item with the given name
    """
    for config_item in config_item_iter(site_config_data):
        if config_item.item.get("name") == name:
            return config_item.item
    return None


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


def is_page_content(site_config_data, raw_config_item):
    """
    Returns True if the given config item describes page content, as opposed to data/configuration

    Args:
        site_config_data (dict): A full site config
        raw_config_item (dict):

    Returns:
        bool: True if the given config item describes page content
    """
    file_target = get_file_target(raw_config_item)
    content_dir = site_config_data.get(
        WEBSITE_CONFIG_CONTENT_DIR_KEY, WEBSITE_CONFIG_DEFAULT_CONTENT_DIR
    )
    return file_target == content_dir or file_target.startswith(f"{content_dir}/")
