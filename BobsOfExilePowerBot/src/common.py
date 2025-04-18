"""Has common types, enums, etc. used throughout the project"""

from typing import Collection, Any, Callable, TypedDict, Protocol, Coroutine
from enum import Enum
from discord.ext import commands


type AnyCoroutine = Coroutine[None| Any, None | Any, None | Any]

type TupList[T] = tuple[T, ...] | list[T]


class Stringable(Protocol):
    def __str__(self) -> str: ...


class CfgSections(Enum):
    MASTER_SECTION = "MASTER"


class CfgMasterOptions(Enum):
    DISCORD_CMD_PREFIX = "DISCORD_CMD_PREFIX"
    DISCORD_TOKEN = "DISCORD_TOKEN"
    TUYA_REGION = "TUYA_REGION"
    TUYA_ACCESS_ID = "TUYA_ACCESS_ID"
    TUYA_ACCESS_SECRET = "TUYA_ACCESS_SECRET"
    TUYA_SWITCH_DEVICE_ID = "TUYA_SWITCH_DEVICE_ID"


type AccessInfo = tuple[bool, tuple[int, ...]]
# ^ bool: is_whitelist : True => Whitelist, False => Blacklist
# ^ tuple[int, ...] : user_ids : discord user IDs to consider for the whitelist/blacklist
type BotContext = commands.Context[commands.Bot]
type CmdInfo = tuple[Callable[..., Any], str, TupList[str]]
# ^        tuple[func,               name, aliases]]
type CmdsRegister = Collection[CmdInfo]
type Event = tuple[Callable[..., Any], bool]
# ^          tuple[event_func,         has_bot_argument]
type EventsRegister = Collection[Event]


type TuyaCommands = dict[str, list[dict[str, Any]]]
type TuyaResponse = dict[str, Any]


class TuyaCloudInfo(TypedDict):
    region: str
    access_id: str
    access_secret: str


class TuyaResponseKeys(Enum):
    # note: Not all responses contain all these keys
    SUCCESS = "success"
    RESULT = "result"


class TuyaResultEntry(TypedDict):
    code: str
    value: Any


class TuyaResultKeys(Enum):
    CODE = "code"
    VALUE = "value"
