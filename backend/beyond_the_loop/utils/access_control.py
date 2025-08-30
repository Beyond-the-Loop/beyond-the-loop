from typing import Optional, List, Dict, Any
from beyond_the_loop.models.users import Users, UserModel
from beyond_the_loop.models.groups import Groups

import json

DEFAULT_USER_PERMISSIONS = {
    "workspace": {
        "knowledge": True,
        "view_prompts": True,
        "edit_prompts": False,
        "view_assistants": True,
        "edit_assistants": False,
        "tools": True,
    },
    "chat": {
        "controls": True,
        "file_upload": True,
        "delete": True,
        "edit": True,
        "temporary": True,
    },
    "features": {
        "web_search": True,
        "image_generation": True,
        "code_interpreter": True,
    },
}


def fill_missing_permissions(
    permissions: Dict[str, Any], default_permissions: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Recursively fills in missing properties in the permissions dictionary
    using the default permissions as a template.
    """
    for key, value in default_permissions.items():
        if key not in permissions:
            permissions[key] = value
        elif isinstance(value, dict) and isinstance(
            permissions[key], dict
        ):  # Both are nested dictionaries
            permissions[key] = fill_missing_permissions(permissions[key], value)

    return permissions


def get_permissions(
    user_id: str,
) -> Dict[str, Any]:
    """
    Get all permissions for a user by combining the permissions of all groups the user is a member of.
    If a permission is defined in multiple groups, the most permissive value is used (True > False).
    Permissions are nested in a dict with the permission key as the key and a boolean as the value.
    """

    def combine_permissions(
        permissions: Dict[str, Any], group_permissions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Combine permissions from multiple groups by taking the most permissive value."""
        for key, value in group_permissions.items():
            if isinstance(value, dict):
                if key not in permissions:
                    permissions[key] = {}
                permissions[key] = combine_permissions(permissions[key], value)
            else:
                if key not in permissions:
                    permissions[key] = value
                else:
                    # Use group permission value if defined, otherwise use regular permission value
                    permissions[key] = value if value is not None else permissions[key]

        return permissions

    user_groups = Groups.get_groups_by_member_id(user_id)

    # Deep copy default permissions to avoid modifying the original dict
    permissions = json.loads(json.dumps(DEFAULT_USER_PERMISSIONS))

    # Combine permissions from all user groups
    for group in user_groups:
        group_permissions = group.permissions

        if group_permissions:
            permissions = combine_permissions(permissions, group_permissions)

    # Ensure all fields from default_permissions are present and filled in
    permissions = fill_missing_permissions(permissions, DEFAULT_USER_PERMISSIONS)

    return permissions


def has_permission(
    user_id: str,
    permission_key: str,
) -> bool:
    """
    Check if a user has a specific permission by checking permissions of the user

    Permission keys can be hierarchical and separated by dots ('.').
    """

    permissions = get_permissions(user_id)

    permission_keys = permission_key.split(".")
    current_permission = permissions

    for key in permission_keys:
        if key not in current_permission:
            return False

        if isinstance(current_permission[key], dict):
            current_permission = current_permission[key]
        else:
            return current_permission[key]

    return False

def has_access(
    user_id: str,
    type: str = "write",
    access_control: Optional[dict] = None,
) -> bool:
    if access_control is None:
        return type == "read"

    user_groups = Groups.get_groups_by_member_id(user_id)
    user_group_ids = [group.id for group in user_groups]
    permission_access = access_control.get(type, {})
    permitted_group_ids = permission_access.get("group_ids", [])
    permitted_user_ids = permission_access.get("user_ids", [])

    return user_id in permitted_user_ids or any(
        group_id in permitted_group_ids for group_id in user_group_ids
    )

# Get all users with access to a resource
def get_users_with_access(
    type: str = "write", access_control: Optional[dict] = None
) -> List[UserModel]:
    if access_control is None:
        return Users.get_users()

    permission_access = access_control.get(type, {})
    permitted_group_ids = permission_access.get("group_ids", [])
    permitted_user_ids = permission_access.get("user_ids", [])

    user_ids_with_access = set(permitted_user_ids)

    for group_id in permitted_group_ids:
        group_user_ids = Groups.get_group_user_ids_by_id(group_id)
        if group_user_ids:
            user_ids_with_access.update(group_user_ids)

    return Users.get_users_by_user_ids(list(user_ids_with_access))
