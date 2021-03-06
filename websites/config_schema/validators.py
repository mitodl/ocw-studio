"""Site config validation functionality to supplement the features that the schema gives us"""
from collections import defaultdict

from yamale import YamaleError
from yamale.schema.validationresults import ValidationResult

from websites.site_config_api import config_item_iter


class AddedSchemaRule:
    @staticmethod
    def apply_rule(data):
        """
        Applies a validation step to the given data

        data (any):
            The data to validate

        Returns:
            list of str: A list of error messages (or an empty list if the data is valid)
        """
        raise NotImplementedError

    @classmethod
    def validate(cls, data, schema_path=None):
        """
        Validates the given data, and raises the error message(s) as a standard Yamale exception if error messages
        are returned.

        Raises:
            YamaleError: A standard Yamale exception
        """
        error_strs = cls.apply_rule(data)
        if error_strs:
            validation_results = [
                ValidationResult(data=None, schema=schema_path, errors=error_strs)
            ]
            raise YamaleError(validation_results)


class CollectionsKeysRule(AddedSchemaRule):
    """Ensures that collections items only define one of a set of mutually-exclusive keys"""

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
                    "{}: Only one of the following keys can be specified for a collection item - {}".format(
                        path, ", ".join(exclusive_keys)
                    )
                ]


class UniqueNamesRule(AddedSchemaRule):
    """Ensures that all config items have unique name values"""

    @staticmethod
    def apply_rule(data):
        name_paths = defaultdict(list)
        for i, config_item in enumerate(config_item_iter(data)):
            name_paths[config_item.item["name"]].append(config_item.path)
        faulty_name_paths = {
            name: paths for name, paths in name_paths.items() if len(paths) > 1
        }
        if faulty_name_paths:
            return [
                "Found duplicate 'name' values. 'name' values must all be unique.\n{}".format(
                    "\n".join(
                        [
                            f"{' ' * 8}'{name}' ({', '.join(paths)})"
                            for name, paths in faulty_name_paths.items()
                        ]
                    )
                )
            ]
        return []
