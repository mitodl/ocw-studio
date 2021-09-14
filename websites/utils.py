"""Websites utils"""
from typing import Any, Dict

from websites import constants


def permissions_group_name_for_role(role, website):
    """Get the website group name for a given role"""
    if role == constants.ROLE_GLOBAL:
        return constants.GLOBAL_ADMIN
    elif role in constants.ROLE_GROUP_MAPPING.keys():
        return f"{constants.ROLE_GROUP_MAPPING[role]}{website.uuid.hex}"
    else:
        raise ValueError(f"Invalid role for a website group: {role}")


def get_dict_field(obj: Dict, field_path: str) -> Any:
    """Return the value of a potentially nested dict path"""
    fields = field_path.split(".")
    current_obj = obj
    for field in fields[:-1]:
        current_obj = current_obj.get(field)
    return current_obj.get(fields[-1])


def set_dict_field(obj: Dict, field_path: str, value: Any):
    """Set the value of a potentially nested dict path"""
    fields = field_path.split(".")
    current_obj = obj
    for field in fields[:-1]:
        current_obj = current_obj.get(field)
    current_obj[fields[-1]] = value


def get_dict_query_field(dict_field_name: str, sub_field: str):
    """Generate django query key for searching a nested json feild"""
    return dict_field_name + "__" + sub_field.replace(".", "__")
