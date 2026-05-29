from abc import ABC, abstractmethod
import asyncio
from typing import Any, Generic, TypeVar, cast
from collections.abc import Sequence, MutableMapping
import shlex
import logging
import asyncclick as click
import enum

from .permission_info import IPermissionInfo, PermissionContext
from .responder import IResponder
from .permission_info import PermissionContext, IPermissionInfo

T = TypeVar("T")


class ILockingComponent(ABC):
    @abstractmethod
    def is_locked(self) -> bool: ...
    @abstractmethod
    async def acquire(self) -> None: ...
    @abstractmethod
    def release(self) -> None: ...


class LockingComponentStandard(ILockingComponent):
    __slots__ = ("lock",)

    lock: asyncio.Lock

    def __init__(self, lock: asyncio.Lock) -> None:
        self.lock = lock

    def is_locked(self) -> bool:
        return self.lock.locked()

    async def acquire(self) -> None:
        await self.lock.acquire()

    def release(self) -> None:
        self.lock.release()


class LockingComponentDummy(ILockingComponent):
    def __int__(self):
        pass

    def is_locked(self) -> bool:
        return False

    async def acquire(self) -> None:
        pass

    def release(self) -> None:
        pass


class ICommandCall(ABC):
    @abstractmethod
    async def call(self) -> None: ...
    @abstractmethod
    def get_locking_component(self) -> ILockingComponent: ...
    @abstractmethod
    def get_permission_info(self) -> IPermissionInfo: ...


class CommandCallBase(Generic[T], ICommandCall):
    """
    Optional base that provides some default implementations
    """

    __slots__ = ("invocation", "responder", "locking_component", "permission_info")

    invocation: T
    responder: IResponder

    locking_component: ILockingComponent
    permission_info: IPermissionInfo

    def __init__(
        self,
        invocation: T,
        responder: IResponder,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
    ) -> None:
        self.invocation = invocation
        self.responder = responder

        self.locking_component = locking_component
        self.permission_info = permission_info

    def get_locking_component(self) -> ILockingComponent:
        return self.locking_component

    def get_permission_info(self) -> IPermissionInfo:
        return self.permission_info


class ICommandCaller(Generic[T], ABC):
    @abstractmethod
    # Additionally returns self due to the way we use click
    def make_invocation(
        self, *args: Any, **kwargs: Any
    ) -> tuple["ICommandCaller[T]", T]: ...
    @abstractmethod
    def make_call(self, invocation: T, responder: IResponder) -> ICommandCall: ...


class CommandCallerBase(ICommandCaller[T]):
    __slots__ = ("locking_component", "permission_info")

    locking_component: ILockingComponent
    permission_info: IPermissionInfo

    def __init__(
        self,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
    ) -> None:
        self.locking_component = locking_component
        self.permission_info = permission_info


class CommandEntry:
    """Holds logic for a command and also used as a representation for that command's logic
    Also holds metadata for parsing its own arguments

    Statically assigned attrs/properties:
    - methods (init, execution-related)
    - parsing metadata
    Dynamically assigned attrs/properties:
    - permission controller"""

    __slots__ = ("name", "command")

    name: str
    command: click.Command

    def __init__(self, name: str, command: click.Command) -> None:
        self.name = name
        self.command = command


class CommandsRegistry:
    """
    Manages a mapping and an internal click group
    """

    __slots__ = (
        "ctx_group",
        "group",
        "entries",
    )

    ctx_group: click.Context
    group: click.Group
    entries: MutableMapping[str, CommandEntry]

    def __init__(
        self,
        group: click.Group,
    ) -> None:
        self.group = group
        self.entries = dict()
        self.ctx_group = click.Context(self.group)

    def add_entry(self, command_entry: CommandEntry) -> None:
        if command_entry.name in self.entries:
            raise CommandsRegistryOverridingEntryError(f"Commands registry entry already exists under this name {command_entry.name=}") # fmt: skip
        self.entries[command_entry.name] = command_entry
        self.group.add_command(cmd=command_entry.command, name=command_entry.name)

    async def call_command(
        self,
        to_run: str,
        author_id: str,
        responder: IResponder,
    ) -> None:
        """-> success (unless error is raised)
        Assumes given to run is not empty
        Doesn't catch click usage errors"""
        # TODO Turn the False return value (indicating not being found) into an error that must be caught

        assert to_run, "To run is an empty string"
        to_run_split: Sequence[str] = shlex.split(to_run, comments=False, posix=True)
        assert len(to_run_split) != 0, "To run splits count is zero"
        cmd_name: str = to_run_split[0]
        cmd_args: Sequence[str] = to_run_split[1:]

        logging.info(f"Calling command | {to_run}")

        if cmd_name not in self.entries:
            raise CommandsRegistryEntryNotFoundError(cmd_name)
        command_entry: CommandEntry = self.entries[cmd_name]

        command: click.Command | None = self.group.get_command(
            self.ctx_group, cmd_name=cmd_name
        )
        assert command is not None, f"The commands registry and click group are desynchronized {command_entry.name=}" # fmt: skip
        ctx_command: click.Context = await command.make_context(
            info_name=None, args=cmd_args, parent=self.ctx_group
        )

        # TODO Improve type safety here
        click_invoked = await command.invoke(ctx_command)
        assert isinstance(click_invoked, tuple)
        click_invoked = cast(tuple[Any, ...], click_invoked)
        assert len(click_invoked) == 2

        caller = click_invoked[0]
        assert isinstance(caller, ICommandCaller)
        caller = cast(ICommandCaller[Any], caller)

        invocation: Any = click_invoked[1]

        call: ICommandCall = caller.make_call(
            invocation=invocation, responder=responder
        )
        permission_component: IPermissionComponent = PermissionComponentDiscord(
            permission_context=PermissionContext(user_id=author_id),
            permission_info=call.get_permission_info(),
        )
        _ = await call_command_featureful(
            call=call,
            responder=responder,
            permissions=permission_component,
            lock=call.get_locking_component(),
        )

    def get_command_help(self, command: str) -> str | None:
        click_command: click.Command | None = self.group.get_command(
            self.ctx_group, command
        )
        if click_command is None:
            return None
        return click_command.get_help(self.ctx_group)

    def get_group_help(self) -> str:
        return self.group.get_help(self.ctx_group)


class CommandsRegistryError(Exception):
    pass


class CommandsRegistryOverridingEntryError(CommandsRegistryError):
    pass


class CommandsRegistryEntryNotFoundError(CommandsRegistryError):
    pass


class IPermissionComponent(ABC):
    @abstractmethod
    def is_allowed(self) -> bool: ...

    @abstractmethod
    def get_required_permission_description(self) -> str: ...


class PermissionComponentDiscord(IPermissionComponent):
    __slots__ = (
        "permission_context",
        "permission_info",
    )

    permission_context: PermissionContext
    permission_info: IPermissionInfo

    def __init__(
        self,
        permission_context: PermissionContext,
        permission_info: IPermissionInfo,
    ) -> None:
        self.permission_context = permission_context
        self.permission_info = permission_info

    def is_allowed(self) -> bool:
        return self.permission_info.check_access(self.permission_context)

    def get_required_permission_description(self) -> str:
        return self.permission_info.get_description()


class PermissionComponentDummy(IPermissionComponent):
    __slots__ = ()

    def __init__(self) -> None:
        pass

    def is_allowed(self) -> bool:
        return True

    def get_required_permission_description(self) -> str:
        return "Any (using dummy permission component)"


class CommandCallFeaturefulResult(enum.Enum):
    SUCCESS = enum.auto()
    FAIL_PERMISSION = enum.auto()
    FAIL_LOCKED = enum.auto()


# TODO Should I really use a result enum or should I use exceptions?


async def call_command_featureful(
    call: ICommandCall,
    responder: IResponder,
    permissions: IPermissionComponent,
    lock: ILockingComponent,
) -> CommandCallFeaturefulResult:
    """Dummy components may be used"""

    # TODO Add logging
    if not permissions.is_allowed():
        required_permission_description: str = (
            permissions.get_required_permission_description()
        )
        await responder.respond(f"Insufficient permissions to access this command. Requires: {required_permission_description}") # fmt: skip
        return CommandCallFeaturefulResult.FAIL_PERMISSION

    if lock.is_locked():
        await responder.respond("An another command is currently in progress. Please try again later.") # fmt: skip
        return CommandCallFeaturefulResult.FAIL_LOCKED

    await lock.acquire()

    base_exception: BaseException | None = None
    try:
        await call.call()
    except Exception as e:
        await responder.respond(f"Command failed due to an error:\n```{repr(e)}```")
        logging.error(f"Command failed due to an error", exc_info=e)
    except BaseException as e:
        base_exception = e

    lock.release()

    if base_exception is not None:
        raise base_exception

    return CommandCallFeaturefulResult.SUCCESS


def simple_setup_cmd(
    name: str,
    click_command: click.Command,
    commands_registry: CommandsRegistry,
) -> None:
    command_entry: CommandEntry = CommandEntry(name=name, command=click_command)

    commands_registry.add_entry(command_entry)
