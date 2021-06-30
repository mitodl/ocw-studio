"""Websites utils"""
import yaml

from websites import constants


def permissions_group_name_for_role(role: str, website: "Website") -> str:
    """Get the website group name for a given role"""
    if role == constants.ROLE_GLOBAL:
        return constants.GLOBAL_ADMIN
    elif role in constants.ROLE_GROUP_MAPPING.keys():
        return f"{constants.ROLE_GROUP_MAPPING[role]}{website.uuid.hex}"
    else:
        raise ValueError(f"Invalid role for a website group: {role}")


def format_site_config_env(website: "Website") -> str:
    """Return a yaml-formatted string containing info for hugo publishing"""
    return yaml.dump(
        {
            "config_path": website.starter.path,
            "config_slug": website.starter.slug,
            "site_slug": website.name,
        }
    )
