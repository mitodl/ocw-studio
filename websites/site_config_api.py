"""API functionality for working with site configs"""

from typing import NamedTuple, Optional


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
