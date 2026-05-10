from abc import ABC, abstractmethod
import asyncio
from typing import Any
from collections.abc import Sequence, MutableMapping
import shlex
import logging
import asyncclick as click

from .permissions import IPermissionInfo, PermissionContext
from .minecraft import MinecraftManager
from .networking import NetworkingHandler
from .power_device import PowerController
from .responder import IResponder
from .permissions import PermissionContext, IPermissionInfo

# I have no clue how to use the component pattern, this is just practice so I can get used to it (I'm probably doing it wrong)


class CallContextGrand:
    # TODO
    # This is TERRIBLE programming. DON'T do this.
    # TODO
    # This class basically allows commands to operate in a "global" scope with access to basically everything (which I hate but whatever, this project is to small to warrant any more sophisticated solutions)
    # I could probably just turn all commands into classes that store what they need in their attributes (especially the things that are considered "grand")

    __slots__ = (
        "minecraft_manager",
        "commands_registry",
        "networking_handler",
        "client_power_controller",
        "commands_lock",
    )

    minecraft_manager: MinecraftManager | None
    commands_registry: "CommandsRegistry | None"
    networking_handler: NetworkingHandler
    client_power_controller: PowerController | None
    commands_lock: asyncio.Lock

    def __init__(
        self,
        minecraft_manager: MinecraftManager | None,
        commands_registry: "CommandsRegistry | None",
        networking_handler: NetworkingHandler,
        client_power_controller: PowerController | None,
        commands_lock: asyncio.Lock,
    ) -> None:
        self.minecraft_manager = minecraft_manager
        self.commands_registry = commands_registry
        self.networking_handler = networking_handler
        self.client_power_controller = client_power_controller
        self.commands_lock = commands_lock


class CommandEntry:
    """Holds logic for a command and also used as a representation for that command's logic
    Also holds metadata for parsing its own arguments

    Statically assigned attrs/properties:
    - methods (init, execution-related)
    - parsing metadata
    Dynamically assigned attrs/properties:
    - permission controller"""

    __slots__ = ("name", "command", "permission_info")

    name: str
    command: click.Command
    permission_info: IPermissionInfo

    def __init__(
        self, name: str, command: click.Command, permission_info: IPermissionInfo
    ) -> None:
        self.name = name
        self.command = command
        self.permission_info = permission_info


class CommandsRegistry:
    """
    Manages an internal click group as well as an internal dict
    """

    __slots__ = ("ctx_group", "group", "entries", "call_context_grand")

    ctx_group: click.Context
    group: click.Group
    entries: MutableMapping[str, CommandEntry]
    call_context_grand: CallContextGrand

    def __init__(
        self,
        group: click.Group,
        call_context_grand: CallContextGrand,
    ) -> None:
        self.group = group
        self.entries = dict()
        self.ctx_group = click.Context(self.group)
        self.call_context_grand = call_context_grand

    def add_entry(self, command_entry: CommandEntry) -> None:
        if command_entry.name in self.entries:
            raise OverridingCommandsRegistryEntryError(command_entry, self, f"Commands registry entry already exists under this name {command_entry.name=}") # fmt: skip
        self.entries[command_entry.name] = command_entry
        self.group.add_command(cmd=command_entry.command, name=command_entry.name)

    async def call_command(
        self,
        to_run: str,
        author_id: str,
        responder: IResponder,
    ) -> bool:
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
            return False
        command_entry: CommandEntry = self.entries[cmd_name]

        command: click.Command | None = self.group.get_command(
            self.ctx_group, cmd_name=cmd_name
        )
        if command is None:
            raise CommandsRegistryDesynchronizationError(command_entry, self, f"The commands registry and click group are desynchronized {command_entry.name=}") # fmt: skip
        ctx_command: click.Context = await command.make_context(
            info_name=None, args=cmd_args, parent=self.ctx_group
        )

        invocation: ICommandInvocationStandard | Any = await command.invoke(ctx_command)

        respect_lock: bool | None = invocation.get_default_respect_locks()
        if respect_lock is None:
            respect_lock = False
        if respect_lock:
            locking_component: ILockingComponent = LockingComponentStandard(
                self.call_context_grand.commands_lock
            )
        else:
            locking_component: ILockingComponent = LockingComponentDummy()

        permission_info_component: IPermissionInfoComponent = (
            PermissionInfoComponentDiscord(
                permission_context=PermissionContext(user_id=author_id),
                permission_info=command_entry.permission_info,
            )
        )

        call: ICommandCall = invocation.make_call(
            responder=responder, call_context_grand=self.call_context_grand
        )

        await call_command_featureful(
            call=call,
            responder=responder,
            permissions=permission_info_component,
            lock=locking_component,
        )

        return True

    def get_command_help(self, command: str) -> str | None:
        click_command: click.Command | None = self.group.get_command(
            self.ctx_group, command
        )
        if click_command is None:
            return None
        return click_command.get_help(self.ctx_group)

    def get_all_help(self) -> str:
        return self.group.get_help(self.ctx_group)


class OverridingCommandsRegistryEntryError(Exception):
    __slots__ = ("entry", "registry")

    entry: CommandEntry
    registry: CommandsRegistry

    def __init__(
        self, entry: CommandEntry, registry: CommandsRegistry, *args: object
    ) -> None:
        super().__init__(*args)
        self.entry = entry
        self.registry = registry


class CommandsRegistryDesynchronizationError(Exception):
    __slots__ = ("entry", "registry")

    entry: CommandEntry
    registry: CommandsRegistry

    def __init__(
        self, entry: CommandEntry, registry: CommandsRegistry, *args: object
    ) -> None:
        super().__init__(*args)
        self.entry = entry
        self.registry = registry


class IPermissionInfoComponent(ABC):
    @abstractmethod
    def is_allowed(self) -> bool: ...

    @abstractmethod
    def get_required_permission_description(self) -> str: ...


class PermissionInfoComponentDiscord(IPermissionInfoComponent):
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


class PermissionInfoComponentDummy(IPermissionInfoComponent):
    __slots__ = ()

    def __init__(self) -> None:
        pass

    def is_allowed(self) -> bool:
        return True

    def get_required_permission_description(self) -> str:
        return "Any (using dummy permission component)"


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


class ICommandInvocationStandard(ABC):
    @abstractmethod
    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> ICommandCall: ...

    @abstractmethod
    def get_default_respect_locks(self) -> bool | None: ...


async def call_command_featureful(
    call: ICommandCall,
    responder: IResponder,
    permissions: IPermissionInfoComponent,
    lock: ILockingComponent,
) -> None:
    """Dummy components may be used"""

    # TODO Add logging
    if not permissions.is_allowed():
        required_permission_description: str = (
            permissions.get_required_permission_description()
        )
        await responder.respond(f"Insufficient permissions to access this command. Requires: {required_permission_description}") # fmt: skip
        return

    if lock.is_locked():
        await responder.respond("An another command is currently in progress. Please try again later.") # fmt: skip
        return

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


def simple_setup_cmd(
    name: str,
    click_command: click.Command,
    commands_registry: CommandsRegistry,
    permission_info: IPermissionInfo,
) -> None:
    command_entry: CommandEntry = CommandEntry(
        name=name, command=click_command, permission_info=permission_info
    )

    commands_registry.add_entry(command_entry)
