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

NAME: str = "servercmd"


@dataclass(frozen=True, slots=True)
class CommandInvocationServerCmd:
    cmd: str
    name: str


class CommandCallServerCmd(CommandCallBase[CommandInvocationServerCmd]):
    minecraft_manager: MinecraftManager

    def __init__(
        self,
        invocation: CommandInvocationServerCmd,
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
            await self.responder.respond(f"Instance is not running. ({entry_name})")
            return
        if entry.get_instance_stopping().get():
            await self.responder.respond(f"Instance is stopping. ({entry_name})")
            return
        startup_phase: int = entry.get_instance_startup_phase().get()
        if startup_phase < 2:
            await self.responder.respond(f"Instance isn't ready yet. (startup phase: {startup_phase}, but must be 2). ({entry_name})") # fmt: skip
            return

        try:
            await entry.send_command(self.invocation.cmd)
        except Exception as e:
            await self.responder.respond(
                f"Got error ({entry_name})!\n```\n{repr(e)}\n```"
            )
        else:
            await self.responder.respond(f"Sent command. ({entry_name})")


class CommandCallerServerCmd(CommandCallerBase[CommandInvocationServerCmd]):
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
        self, cmd: str, name: str
    ) -> tuple["CommandCallerServerCmd", CommandInvocationServerCmd]:
        return (self, CommandInvocationServerCmd(cmd=cmd, name=name))

    def make_call(
        self, invocation: CommandInvocationServerCmd, responder: IResponder
    ) -> CommandCallServerCmd:
        return CommandCallServerCmd(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            minecraft_manager=self.minecraft_manager,
        )


def setup_cmd_servercmd(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
    default_target: str,
    minecraft_manager: MinecraftManager,
) -> None:
    caller: CommandCallerServerCmd = CommandCallerServerCmd(
        locking_component=locking_component,
        permission_info=permission_info,
        minecraft_manager=minecraft_manager,
    )

    params: list[click.Parameter] = [
        click.Argument(["cmd"], type=str, required=True),
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
