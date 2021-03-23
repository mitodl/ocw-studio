"""Site config validation functionality to supplement the features that the schema gives us"""
from yamale import YamaleError
from yamale.schema.validationresults import ValidationResult


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
        exclusive_keys = {"folder", "files", "file"}
        for i, collection_item in enumerate(collections):
            matching_keys = set(collection_item.keys()).intersection(exclusive_keys)
            if len(matching_keys) > 1:
                path = f"collections.{i}"
                return [
                    "{}: Only one of the following keys can be specified for a collection item - {}".format(
                        path, ", ".join(exclusive_keys)
                    )
                ]
