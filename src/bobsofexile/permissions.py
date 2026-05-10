from collections.abc import Sequence
from abc import abstractmethod, ABC


class PermissionContext:
    __slots__ = ("user_id",)

    user_id: str

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id


class IPermissionInfo(ABC):
    @abstractmethod
    def check_access(self, permission_context: PermissionContext) -> bool: ...
    @abstractmethod
    def get_description(self) -> str: ...


class PermissionInfo(IPermissionInfo):
    __slots__ = ("_description", "whitelist_enabled", "users")

    _description: str
    whitelist_enabled: bool
    users: Sequence[str]

    def __init__(
        self, whitelist_enabled: bool, users: Sequence[str], description: str
    ) -> None:
        """
        Whitelist disabled -> users is a blacklist
        Whitelist enabled -> users is a whitelist
        """
        self._description = description
        self.whitelist_enabled = whitelist_enabled
        self.users = users

    def check_access(self, permission_context: PermissionContext) -> bool:
        in_users: bool = permission_context.user_id in self.users
        if self.whitelist_enabled:
            return in_users
        return not in_users

    def get_description(self) -> str:
        return self._description
