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

NAME: str = "help"


@dataclass(frozen=True, slots=True)
class CommandInvocationHelp:
    cmd_or_empty: str | None


class CommandCallHelp(CommandCallBase[CommandInvocationHelp]):
    commands_registry: CommandsRegistry

    def __init__(
        self,
        invocation: CommandInvocationHelp,
        responder: IResponder,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        commands_registry: CommandsRegistry,
    ) -> None:
        super().__init__(
            invocation=invocation,
            responder=responder,
            locking_component=locking_component,
            permission_info=permission_info,
        )
        self.commands_registry = commands_registry

    async def call(self) -> None:
        if self.invocation.cmd_or_empty is not None:
            cmd_help: str | None = self.commands_registry.get_command_help(
                command=self.invocation.cmd_or_empty
            )
            if cmd_help is None:
                await self.responder.respond("No command found")
            else:
                await self.responder.respond(cmd_help)
        else:
            await self.responder.respond(self.commands_registry.get_group_help())


class CommandCallerHelp(CommandCallerBase[CommandInvocationHelp]):
    commands_registry: CommandsRegistry

    def __init__(
        self,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        commands_registry: CommandsRegistry,
    ) -> None:
        super().__init__(
            locking_component=locking_component, permission_info=permission_info
        )
        self.commands_registry = commands_registry

    def make_invocation(
        self, cmd_or_empty: str | None
    ) -> tuple["CommandCallerHelp", CommandInvocationHelp]:
        return (self, CommandInvocationHelp(cmd_or_empty=cmd_or_empty))

    def make_call(
        self, invocation: CommandInvocationHelp, responder: IResponder
    ) -> CommandCallHelp:
        return CommandCallHelp(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            commands_registry=self.commands_registry,
        )


def setup_cmd_help(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
) -> None:
    caller: CommandCallerHelp = CommandCallerHelp(
        locking_component=locking_component,
        permission_info=permission_info,
        commands_registry=commands_registry,
    )

    params: list[click.Parameter] = [
        click.Argument(["cmd_or_empty"], type=str, required=False, default=None)
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
