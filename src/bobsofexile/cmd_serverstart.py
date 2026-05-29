from dataclasses import dataclass

import asyncclick as click

from .commands import (
    simple_setup_cmd,
    ILockingComponent,
    CommandsRegistry,
    CommandCallBase,
    CommandCallerBase,
)
from .responder import IResponder
from .permission_info import IPermissionInfo

from .minecraft import (
    MinecraftInstanceEntry,
    MinecraftEntryStartPreconfiguration,
    MinecraftManager,
)

NAME: str = "serverstart"


@dataclass(frozen=True, slots=True)
class CommandInvocationServerStart:
    name: str


class CommandCallServerStart(CommandCallBase[CommandInvocationServerStart]):
    minecraft_manager: MinecraftManager

    def __init__(
        self,
        invocation: CommandInvocationServerStart,
        responder: IResponder,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        minecraft_manager: MinecraftManager,
    ) -> None:
        super().__init__(
            invocation=invocation,
            responder=responder,
            locking_component=locking_component,
            permission_info=permission_info,
        )
        self.minecraft_manager = minecraft_manager

    async def call(self) -> None:
        entry: MinecraftInstanceEntry | None = self.minecraft_manager.get_entry(
            self.invocation.name
        )
        if entry is None:
            await self.responder.respond(
                f"No such minecraft entry. ({self.invocation.name})"
            )
            return
        entry_name: str = entry.name
        if entry.get_running().get():
            await self.responder.respond(f"Instance is already running. ({entry_name})")
            return
        entry_preconfiguration: MinecraftEntryStartPreconfiguration | None = (
            self.minecraft_manager.get_entry_start_preconfiguration(
                self.invocation.name
            )
        )
        if entry_preconfiguration is None:
            await self.responder.respond(f"There is no start preconfiguration for this entry. ({entry_name})") # fmt: skip
            return

        msg_starting_server: str = (
            f"Starting server ({entry_name})... You can `poweroff` the OS later after you're done playing."
            "\n-# Powering off is optional because there's an automatic system for it in-place"
        )

        await self.responder.respond(msg_starting_server)

        async def on_empty() -> None:
            await self.responder.respond(f"Server is empty. ({entry_name})")

        async def on_empty_prolonged() -> None:
            await self.responder.respond(f"Stopping instance due to inactivity. ({entry_name})") # fmt: skip

        async def on_exit() -> None:
            await self.responder.respond(f"Server exit. ({entry_name})")

        async def on_entry_started() -> None:
            await self.responder.respond(f"Entry started.")

        async def on_instance_stopping() -> None:
            await self.responder.respond(f"Instance stopping. ({entry_name})")

        await self.minecraft_manager.start_entry_with_preconfiguration(
            entry=entry,
            preconfiguration=entry_preconfiguration,
            on_empty_hooks=[on_empty],
            on_empty_prolonged_hooks=[on_empty_prolonged],
            on_entry_finish_hooks=[on_exit],
            on_entry_started_hooks=[on_entry_started],
            on_instance_stopping_hooks=[on_instance_stopping],
        )


class CommandCallerServerStart(CommandCallerBase[CommandInvocationServerStart]):
    minecraft_manager: MinecraftManager

    def __init__(
        self,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        minecraft_manager: MinecraftManager,
    ) -> None:
        super().__init__(
            locking_component=locking_component, permission_info=permission_info
        )
        self.minecraft_manager = minecraft_manager

    def make_invocation(
        self, name: str
    ) -> tuple["CommandCallerServerStart", CommandInvocationServerStart]:
        return (self, CommandInvocationServerStart(name=name))

    def make_call(
        self, invocation: CommandInvocationServerStart, responder: IResponder
    ) -> CommandCallServerStart:
        return CommandCallServerStart(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            minecraft_manager=self.minecraft_manager,
        )


def setup_cmd_serverstart(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
    default_target: str,
    minecraft_manager: MinecraftManager,
) -> None:
    caller: CommandCallerServerStart = CommandCallerServerStart(
        locking_component=locking_component,
        permission_info=permission_info,
        minecraft_manager=minecraft_manager,
    )

    params: list[click.Parameter] = [
        click.Option(["-n", "--name"], type=str, required=False, default=default_target)
    ]
    command: click.Command = click.Command(
        name=NAME,
        callback=caller.make_invocation,
        add_help_option=False,
        params=params,
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
    )
