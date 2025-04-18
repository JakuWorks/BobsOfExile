"""File with common types, enums, etc. used throughout the project"""

from typing import (
    Any,
    Collection,
    Callable,
    Coroutine,
    NamedTuple,
    Protocol,
    Self,
    SupportsIndex,
    overload,
    runtime_checkable,
)
import enum
from psutil._common import scpufreq  # type: ignore
from discord.ext import commands
import psutil


class Platform(enum.Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


@runtime_checkable
class SupportsGetItem(Protocol):
    @overload
    def __getitem__(self, i: SupportsIndex, /) -> Self: ...
    @overload
    def __getitem__(self, s: slice) -> Self: ...


# Psutil's definition of svmem (their type for mem) depends on your current system
# And I don't think making system-conditional imports for a small project is a good idea
# So let's just use the properties of svmem that are universal across platforms
class RamInfo(NamedTuple):
    total: int
    available: int
    percent: float
    used: int
    free: int


class SwapInfo(NamedTuple):
    total: int
    percent: float
    used: int
    free: int


class ProcActionStatus(enum.Enum):
    ACCESS_DENIED = 'access_denied'
    NO_SUCH_PROCESS = 'no_such_process'
    ZOMBIE_PROCESS = 'zombie_process'


class ProcActionInfo:
    pass


class ProcInfo:
    proc: psutil.Process
    cpu_use: float | None
    ram_use: float | None

    def __init__(self, proc: psutil.Process) -> None:
        self.proc = proc
        self.cpu_use = None
        self.ram_use = None


Context = commands.Context[commands.Bot]

type BotContext = commands.Context[commands.Bot]
type AccessInfo = tuple[bool, tuple[int, ...]]
# ^ bool: is_whitelist : True => Whitelist, False => Blacklist
# ^ tuple[int, ...] : user_ids : discord user IDs to consider for the whitelist/blacklist

type EventEntry = tuple[Callable[..., Coroutine[Any, Any, Any]], bool]
# Collection[tuple[func, need_bot_context]]
type EventsRegister = Collection[EventEntry]


type SimpleCommand = Callable[..., Coroutine[Any, Any, Any]]
type CommandInfo = tuple[
    bool, str, Collection[str], Collection[Platform], SimpleCommand
]
type CommandsRegister = Collection[CommandInfo]
# Collection[tuple[enabled, name, aliases, supported_platforms, func]]

type PercpuFreq = tuple[int, scpufreq]
type PercpuFreqs = Collection[PercpuFreq]
type PercpuUse = tuple[int, float]
type PercpuUses = Collection[PercpuUse]
type PercpuFreqUse = tuple[int, scpufreq, float]
type PercpuFreqsUses = Collection[PercpuFreqUse]


class SupportsRichComparison_(Protocol):
    def __eq__(self, value: object, /) -> bool: ...
    def __ne__(self, value: object, /) -> bool: ...
    def __gt__(self, value: Self, /) -> bool: ...
    def __ge__(self, value: Self, /) -> bool: ...
    def __lt__(self, value: Self, /) -> bool: ...
    def __le__(self, value: Self, /) -> bool: ...


a: SupportsRichComparison_ = 1
