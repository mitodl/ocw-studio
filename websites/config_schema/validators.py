"""Site config validation functionality to supplement the features that the schema gives us"""  # noqa: E501

from collections import defaultdict

from mitol.common.utils import first_or_none, partition_to_lists
from yamale import YamaleError
from yamale.schema.validationresults import ValidationResult

from websites.constants import CONTENT_MENU_FIELD
from websites.site_config_api import SiteConfig


class AddedSchemaRule:
    """
    Class for validating site config schema rules
    """

    @staticmethod
    def apply_rule(data):
        """
        Applies a validation step to the given data

        data (any):
            The data to validate

        Returns:
            list of str: A list of error messages (or an empty list if the data is valid)
        """  # noqa: D401, E501
        raise NotImplementedError

    @classmethod
    def validate(cls, data, schema_path=None):
        """
        Validates the given data, and raises the error message(s) as a standard Yamale exception if error messages
        are returned.

        Raises:
            YamaleError: A standard Yamale exception
        """  # noqa: D401, E501
        error_strs = cls.apply_rule(data)
        if error_strs:
            validation_results = [
                ValidationResult(data=None, schema=schema_path, errors=error_strs)
            ]
            raise YamaleError(validation_results)


class CollectionsKeysRule(AddedSchemaRule):
    """Ensures that collections items must define one of a set of mutually-exclusive keys for files and folders"""  # noqa: E501

    @staticmethod
    def apply_rule(data):
        collections = data.get("collections")
        if not collections:
            return []
        exclusive_keys = {"folder", "files"}
        for i, collection_item in enumerate(collections):
            matching_keys = set(collection_item.keys()).intersection(exclusive_keys)
            if len(matching_keys) > 1:
                path = f"collections.{i}"
                return [
                    "{}: Only one of the following keys can be specified for a collection item - {}".format(  # noqa: E501
                        path, ", ".join(exclusive_keys)
                    )
                ]
            if len(matching_keys) < 1:
                path = f"collections.{i}"
                return [
                    f"{path}: A collection must have one of the following keys: {', '.join(sorted(exclusive_keys))}"  # noqa: E501
                ]
        return None


class UniqueNamesRule(AddedSchemaRule):
    """Ensures that all config items have unique 'name' values"""

    @staticmethod
    def apply_rule(data):
        name_paths = defaultdict(list)
        for _, config_item in enumerate(SiteConfig(data).iter_items()):
            name_paths[config_item.item["name"]].append(config_item.path)
        faulty_name_paths = {
            name: paths for name, paths in name_paths.items() if len(paths) > 1
        }
        if faulty_name_paths:
            return [
                "Found duplicate 'name' values. 'name' values must all be unique.\n{}".format(  # noqa: E501
                    "\n".join(
                        [
                            f"{' ' * 8}'{name}' ({', '.join(paths)})"
                            for name, paths in faulty_name_paths.items()
                        ]
                    )
                )
            ]
        return []


class ContentFolderRule(AddedSchemaRule):
    """
    Ensures that the 'folder' value for every config item points to the content directory described in the site
    config (or the default).
    """  # noqa: E501

    @staticmethod
    def apply_rule(data):
        faulty_paths = {}
        site_config = SiteConfig(data)
        for _, config_item in enumerate(site_config.iter_items()):
            if config_item.is_folder_item() and not site_config.is_page_content(
                config_item
            ):
                faulty_paths[config_item.name] = config_item.path
        if faulty_paths:
            return [
                "Found 'folder' item(s) that do not point to the content directory ({}).\n{}".format(  # noqa: E501
                    site_config.content_dir,
                    "\n".join(
                        [
                            f"{' ' * 8}'{name}' ({path})"
                            for name, path in faulty_paths.items()
                        ]
                    ),
                )
            ]
        return []


class RequiredTitleRule(AddedSchemaRule):
    """
    Ensures that if a config item includes a "title" field, it is set to required and has the correct type.
    """  # noqa: E501

    @staticmethod
    def apply_rule(data):
        faulty_paths = {}
        site_config = SiteConfig(data)
        for _, config_item in enumerate(site_config.iter_items()):
            title_field = first_or_none(
                [field for field in config_item.fields if field["name"] == "title"]
            )
            if title_field is not None and (
                title_field.get("required", False) is False
                or title_field.get("widget", "string") != "string"
            ):
                faulty_paths[config_item.name] = config_item.path
        if faulty_paths:
            return [
                "'title' fields must use the 'string' widget, and must be set to be required.\n{}".format(  # noqa: E501
                    "\n".join(
                        [
                            f"{' ' * 8}'{name}' ({path})"
                            for name, path in faulty_paths.items()
                        ]
                    ),
                )
            ]
        return []


class MenuOnlyRule(AddedSchemaRule):
    """
    Ensures that a config item with a "menu" field has no other field types besides "menu"
    """  # noqa: E501

    @staticmethod
    def apply_rule(data):
        faulty_path_tuples = {}
        site_config = SiteConfig(data)
        for _, config_item in enumerate(site_config.iter_items()):
            non_menu_fields, menu_fields = partition_to_lists(
                config_item.fields,
                predicate=lambda field: field["widget"] == CONTENT_MENU_FIELD,
            )
            if not menu_fields:
                continue
            if non_menu_fields:
                faulty_path_tuples[config_item.name] = (
                    config_item.path,
                    ", ".join([field["widget"] for field in non_menu_fields]),
                )
        if faulty_path_tuples:
            return [
                "Config with 'menu' fields must not have any fields with other widget types.\n{}".format(  # noqa: E501
                    "\n".join(
                        [
                            f"{' ' * 8}'{name}' ({path_fields_tuple[0]}) - widgets: {path_fields_tuple[1]}"  # noqa: E501
                            for name, path_fields_tuple in faulty_path_tuples.items()
                        ]
                    ),
                )
            ]
        return []
