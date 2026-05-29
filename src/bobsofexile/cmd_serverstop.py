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

from .minecraft import MinecraftInstanceEntry, MinecraftManager

NAME: str = "serverstop"


@dataclass(frozen=True, slots=True)
class CommandInvocationServerStop:
    name: str


class CommandCallServerStop(CommandCallBase[CommandInvocationServerStop]):
    minecraft_manager: MinecraftManager

    def __init__(
        self,
        invocation: CommandInvocationServerStop,
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
        if not entry.get_running().get():
            await self.responder.respond(f"This server is not running. ({entry_name})")
            return
        if entry.get_instance_stopping().get():
            await self.responder.respond(
                f"This server is already stopping. ({entry_name})"
            )
            return
        await self.responder.respond(f"The server will stop soon. ({entry_name})")
        entry.stop()


class CommandCallerServerStop(CommandCallerBase[CommandInvocationServerStop]):
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
    ) -> tuple["CommandCallerServerStop", CommandInvocationServerStop]:
        return (self, CommandInvocationServerStop(name=name))

    def make_call(
        self, invocation: CommandInvocationServerStop, responder: IResponder
    ) -> CommandCallServerStop:
        return CommandCallServerStop(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            minecraft_manager=self.minecraft_manager,
        )


def setup_cmd_serverstop(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
    default_target: str,
    minecraft_manager: MinecraftManager,
) -> None:
    caller: CommandCallerServerStop = CommandCallerServerStop(
        locking_component=locking_component,
        permission_info=permission_info,
        minecraft_manager=minecraft_manager,
    )

    params: list[click.Parameter] = [
        click.Option(
            ["-n", "--name"], type=str, required=False, default=default_target
        ),
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
