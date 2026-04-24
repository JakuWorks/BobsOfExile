from collections.abc import Sequence, MutableMapping
import shlex
import logging
import asyncio

import asyncclick as click
import discord

from .networking import NetworkingHandler
from .permissions import PermissionResolver
from .minecraft import MinecraftInstance, MinecraftContext
from .clientpower import PowerController


class CommandEntry:
    """Holds logic for a command and also used as a representation for that command's logic
    Also holds metadata for parsing its own arguments

    Statically assigned attrs/properties:
    - methods (init, execution-related)
    - parsing metadata
    Dynamically assigned attrs/properties:
    - permission controller"""

    __slots__ = ("name", "command", "call_context_old")

    name: str
    command: click.Command
    call_context_old: "CallContextOld"

    def __init__(
        self, name: str, command: click.Command, call_context_old: "CallContextOld"
    ) -> None:
        self.name = name
        self.command = command
        self.call_context_old = call_context_old


class CommandsRegistry:
    """Manages an internal click group as well as an internal dict"""

    __slots__ = {"ctx_group", "group", "entries", "call_context_grand"}

    ctx_group: click.Context
    group: click.Group
    entries: MutableMapping[str, CommandEntry]
    call_context_grand: "CallContextGrand"

    def __init__(
        self,
        group: click.Group,
        minecraft_context: MinecraftContext,
        networking_handler: NetworkingHandler,
        client_power_controller: PowerController | None,
        commands_lock: asyncio.Lock,
    ) -> None:
        self.group = group
        self.entries = dict()
        self.call_context_grand = CallContextGrand(
            minecraft_context=minecraft_context,
            commands_registry=self,
            networking_handler=networking_handler,
            client_power_controller=client_power_controller,
            commands_lock=commands_lock,
        )
        self.ctx_group = click.Context(self.group)

    def add_entry(self, command_entry: CommandEntry) -> None:
        if command_entry.name in self.entries:
            raise OverridingCommandsRegistryEntryError(command_entry, self, f"Commands registry entry already exists under this name {command_entry.name=}") # fmt: skip
        self.entries[command_entry.name] = command_entry
        self.group.add_command(cmd=command_entry.command, name=command_entry.name)

    async def call_command(
        self, to_run: str, call_context_young: "CallContextYoung"
    ) -> bool:
        """-> success (unless error is raised)
        Assumes given to run is not empty
        Doesn't catch click usage errors"""

        assert to_run, "To run is an empty string"
        to_run_split: Sequence[str] = shlex.split(to_run, comments=False, posix=True)
        assert len(to_run_split) != 0, "To run splits count is zero"
        cmd_name: str = to_run_split[0]
        cmd_args: Sequence[str] = to_run_split[1:]

        logging.info(f"Calling command | {to_run}")

        if cmd_name not in self.entries:
            return False
        command_entry: CommandEntry = self.entries[cmd_name]
        call_context: CallContext = CallContext(
            self.call_context_grand, command_entry.call_context_old, call_context_young
        )

        command: click.Command | None = self.group.get_command(
            self.ctx_group, cmd_name=cmd_name
        )
        if command is None:
            raise CommandsRegistryDesynchronizationError(command_entry, self, f"The commands registry and click group are desynchronized {command_entry.name=}") # fmt: skip
        ctx_command: click.Context = await command.make_context(
            info_name=None, args=cmd_args, parent=self.ctx_group
        )
        ctx_command.obj = call_context
        await command.invoke(ctx_command)
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


class CallContextGrand:
    __slots__ = (
        "minecraft_context",
        "commands_registry",
        "networking_handler",
        "client_power_controller",
        "commands_lock",
    )

    minecraft_context: MinecraftContext
    commands_registry: CommandsRegistry
    networking_handler: NetworkingHandler
    client_power_controller: PowerController | None
    commands_lock: asyncio.Lock

    def __init__(
        self,
        minecraft_context: MinecraftContext,
        commands_registry: CommandsRegistry,
        networking_handler: NetworkingHandler,
        client_power_controller: PowerController | None,
        commands_lock: asyncio.Lock,
    ) -> None:
        self.minecraft_context = minecraft_context
        self.commands_registry = commands_registry
        self.networking_handler = networking_handler
        self.client_power_controller = client_power_controller
        self.commands_lock = commands_lock

    @property
    def server_instance(self) -> MinecraftInstance | None:
        return self.minecraft_context.server_instance

    @server_instance.setter
    def server_instance(self, val: MinecraftInstance | None) -> None:
        self.minecraft_context.server_instance = val


class CallContextOld:
    __slots__ = ("permission_resolver",)

    permission_resolver: PermissionResolver

    def __init__(self, permission_resolver: PermissionResolver) -> None:
        self.permission_resolver = permission_resolver


class CallContextYoung:
    __slots__ = ("message_context", "respect_command_lock")

    message_context: discord.Message
    respect_command_lock: bool

    def __init__(
        self, message_context: discord.Message, respect_command_lock: bool
    ) -> None:
        self.message_context = message_context
        self.respect_command_lock = respect_command_lock


class CallContext:
    # TODO
    # This class basically allows commands to operate in a "global" scope with access to basically everything (which I hate but whatever, this project is to small to warrant any more sophisticated solutions)
    # I could probably just turn all commands into classes that store what they need in their attributes (especially the things that are considered "grand" now)
    # I may make the switch if I deem it necessary; the current approach is good enough for now at least.
    # Thankfully, I am not using discord's commands framework (asyncclick is doing the command parsing and dispatching) so I'm free of their complications.
    __slots__ = ("grand", "old", "young")

    grand: CallContextGrand
    old: CallContextOld
    young: CallContextYoung

    def __init__(
        self, grand: CallContextGrand, old: CallContextOld, young: CallContextYoung
    ) -> None:
        self.grand = grand
        self.old = old
        self.young = young
