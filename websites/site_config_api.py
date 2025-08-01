"""API functionality for working with site configs"""

from collections.abc import Iterator
from dataclasses import dataclass

from django.utils.functional import cached_property

from main.utils import remove_trailing_slashes
from websites.constants import (
    WEBSITE_CONFIG_CONTENT_DIR_KEY,
    WEBSITE_CONFIG_DEFAULT_CONTENT_DIR,
    WEBSITE_CONFIG_ROOT_URL_PATH_KEY,
    WEBSITE_CONFIG_SITE_URL_FORMAT_KEY,
)


@dataclass
class ConfigItem:
    """Utility class for describing an individual site config item"""

    item: dict
    parent_item: dict | None = None
    path: str = ""

    @property
    def file_target(self) -> str | None:
        """
        Returns the destination folder/directory if this is a folder-type config item, or the full destination filepath
        if this is a file-type config item.
        """  # noqa: E501
        return self.item.get("folder") or self.item.get("file")

    def has_file_target(self) -> bool:
        """Returns True if this config item has a file/folder target"""  # noqa: D401
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
        """Returns True if this config item has a folder target"""  # noqa: D401
        return "folder" in self.item

    def is_file_item(self) -> bool:
        """Returns True if this config item has a file target"""  # noqa: D401
        return "file" in self.item

    def iter_fields(
        self,
        only_cross_site: bool = False,  # noqa: FBT001, FBT002
    ) -> Iterator["ConfigField"]:
        """
        Yields ConfigField for each field.

        Args:
            only_cross_site (bool): Whether or not to yield only cross site fields.

        Yields:
            Iterator[ConfigField]: A generator that yields ConfigField.
        """  # noqa: D401
        for field in self.fields:
            if not only_cross_site or field.get("cross_site", False):
                yield ConfigField(field)


@dataclass
class ConfigField:
    """Utility class for describing an individual site config field"""

    field: dict
    parent_field: dict | None = None


class SiteConfig:
    """Utility class for parsing and introspecting site configs"""

    def __init__(self, raw_data):
        self.raw_data = raw_data

    @cached_property
    def content_dir(self) -> str:
        """
        Returns the content directory described in the site config, or the default if that directory isn't included
        """  # noqa: D401, E501
        return (
            self.raw_data.get(WEBSITE_CONFIG_CONTENT_DIR_KEY)
            or WEBSITE_CONFIG_DEFAULT_CONTENT_DIR
        )

    @cached_property
    def root_url_path(self) -> str:
        """
        Returns the root url path described in the site config
        """  # noqa: D401
        return self.raw_data.get(WEBSITE_CONFIG_ROOT_URL_PATH_KEY, "").strip("/")

    @cached_property
    def site_url_format(self) -> str:
        """
        Returns the site url format described in the site config
        """  # noqa: D401
        return self.raw_data.get(WEBSITE_CONFIG_SITE_URL_FORMAT_KEY, "").strip("/")

    def iter_items(self) -> Iterator[ConfigItem]:
        """Yields all config items for which users can enter data"""  # noqa: D401
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

    def iter_fields(self) -> Iterator[ConfigField]:
        """Yield all fields in the configuration"""
        for item in self.iter_items():
            yield from self.iter_item_fields(item)

    def iter_item_fields(self, item: ConfigItem) -> Iterator[ConfigField]:
        """Yield all fields in the configuration"""
        for field in item.fields:
            yield ConfigField(field=field, parent_field=None)

            for inner_field in field.get("fields", []):
                yield ConfigField(field=inner_field, parent_field=field)

    def find_item_by_name(self, name: str) -> ConfigItem | None:
        """Finds a config item in the site config with a matching 'name' value"""  # noqa: D401
        for config_item in self.iter_items():
            if config_item.item.get("name") == name:
                return config_item
        return None

    def generate_item_metadata(
        self,
        name: str,
        cls: object = None,
        use_defaults=False,  # noqa: FBT002
        values: dict | None = None,
    ) -> dict:
        """Generate a metadata dict with blank keys for the specified item. If
        use_defaults is True, fill the keys with default values from config.
        """
        values = values or {}
        item_dict = {}
        item = self.find_item_by_name(name)

        def get_leaf_field_value(config_field: ConfigField):
            key = config_field.field["name"]
            if values.get(key) is not None:
                return values.get(key)
            if use_defaults and config_field.field.get("default") is not None:
                return config_field.field.get("default")
            if config_field.field.get("multiple"):
                return []
            return ""

        if not item:
            return item_dict
        for config_field in self.iter_item_fields(item):
            key = config_field.field["name"]
            # Do not add class/object attributes to the metadata (ex: WebsiteContent.title)  # noqa: E501
            if not cls or not hasattr(cls, key):
                subfields = config_field.field.get("fields")
                if subfields:
                    item_dict[key] = {}
                else:
                    value = get_leaf_field_value(config_field)
                    if config_field.parent_field is None:
                        item_dict[key] = value
                    else:
                        parent_field = config_field.parent_field["name"]
                        item_dict[parent_field] = item_dict.get(parent_field, {})
                        item_dict[parent_field][key] = value
        return item_dict

    def find_item_by_filepath(self, filepath: str) -> ConfigItem | None:
        """Finds a config item in the site config with a matching 'file' value"""  # noqa: D401
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
        """  # noqa: D401, E501
        file_target = config_item.file_target
        return file_target is not None and (
            file_target == self.content_dir
            or file_target.startswith(f"{self.content_dir}/")
        )

    def find_file_field(self, config_item: ConfigItem) -> dict:
        """Return the file field for a config item if it exists"""
        return next(
            filter(lambda y: y.get("widget") == "file", config_item.fields), None
        )
