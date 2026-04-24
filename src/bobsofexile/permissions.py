from collections.abc import Sequence
from typing import Protocol
from abc import abstractmethod


class PermissionContext:
    __slots__ = ("user_id",)
    user_id: str

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id


class PermissionResolver(Protocol):
    description: str

    @abstractmethod
    def check_access(self, permission_context: PermissionContext) -> bool: ...


# TODO Should I remove permissions registry since it's unused?

# class PermissionsRegistry:
#     """Stores and uses permission entries
#     Each permission entry consists of a name and and info"""

#     entries: MutableMapping[str, PermissionInfo]

#     def __init__(self) -> None:
#         self.entries = dict()

#     def add_entry(self, name: str, info: PermissionInfo) -> None:
#         self.entries[name] = info

#     def check_access(self, context: PermissionContext) -> bool:
#         """May raise a missing permission entry error"""
#         permission_info: PermissionInfo | None = self.entries.get(context.user_id)
#         if permission_info is None:
#             raise MissingPermissionEntryError(
#                 context,
#                 self,
#                 f"The permission entry for key {context.user_id=} is missing",
#             )
#         return permission_info.check_access(context.user_id)


# class MissingPermissionEntryError(Exception):
#     context: PermissionContext
#     registry: PermissionsRegistry

# def __init__(
#     self, context: PermissionContext, registry: PermissionsRegistry, *args: object
# ) -> None:
#     super().__init__(*args)
#     self.context = context
#     self.registry = registry


class PermissionInfo(PermissionResolver):
    __slots__ = ("description", "whitelist_enabled", "users")

    description: str
    whitelist_enabled: bool
    users: Sequence[str]

    def __init__(
        self, whitelist_enabled: bool, users: Sequence[str], description: str
    ) -> None:
        """Whitelist disabled -> users is a blacklist
        Whitelist enabled -> users is a whitelist"""
        self.description = description
        self.whitelist_enabled = whitelist_enabled
        self.users = users

    def check_access(self, permission_context: PermissionContext) -> bool:
        in_users: bool = permission_context.user_id in self.users
        if self.whitelist_enabled:
            return in_users
        return not in_users
