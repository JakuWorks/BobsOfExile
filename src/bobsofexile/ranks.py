from collections.abc import MutableSequence, Sequence
import logging

from .hardcoded import (
    ENV_KEY_RANK_TRUSTED_USERS,
    ENV_KEY_RANK_OWNER_USERS,
    BOT_RANKS_SEPARATOR,
)
from .permissions import PermissionInfo
from .main_convenience import get_env_or_error


def owners_from_environment() -> list[str]:
    owner_raw: str = get_env_or_error(ENV_KEY_RANK_OWNER_USERS)
    owners: list[str] = owner_raw.split(BOT_RANKS_SEPARATOR)
    return owners


def trusted_from_environment() -> list[str]:
    trusted_raw: str = get_env_or_error(ENV_KEY_RANK_TRUSTED_USERS)
    trusted: list[str] = trusted_raw.split(BOT_RANKS_SEPARATOR)
    return trusted


class RanksRegistry:
    __slots__ = ("trusted", "owner")

    trusted: MutableSequence[str]
    owner: MutableSequence[str]

    def __init__(self) -> None:
        self.trusted = list()
        self.owner = list()

    def add_trusted(self, trusted: Sequence[str]) -> None:
        logging.info("Extending trusted rank: " + ",".join(trusted))
        self.trusted.extend(trusted)

    def add_owners(self, owners: Sequence[str]) -> None:
        logging.info("Extending owners rank: " + ",".join(owners))
        self.owner.extend(owners)

    def get_no_one_permission_info(self) -> PermissionInfo:
        return PermissionInfo(whitelist_enabled=True, users=[], description="No one")

    def get_everyone_permission_info(self) -> PermissionInfo:
        return PermissionInfo(whitelist_enabled=False, users=[], description="Everyone")

    def get_trusted_permission_info(self) -> PermissionInfo:
        return PermissionInfo(
            whitelist_enabled=True, users=self.trusted, description="Trusted"
        )

    def get_owner_permission_info(self) -> PermissionInfo:
        return PermissionInfo(
            whitelist_enabled=True, users=self.owner, description="Owner"
        )
