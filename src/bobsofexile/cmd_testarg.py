from dataclasses import dataclass
import logging

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

NAME: str = "testarg"


@dataclass(frozen=True, slots=True)
class CommandInvocationTestArg:
    testingargument: str
    testingoption: str


class CommandCallTestArg(CommandCallBase[CommandInvocationTestArg]):
    def __init__(
        self,
        invocation: CommandInvocationTestArg,
        responder: IResponder,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
    ) -> None:
        super().__init__(
            invocation=invocation,
            responder=responder,
            locking_component=locking_component,
            permission_info=permission_info,
        )

    async def call(self) -> None:
        msg: str = f"Testing argument: {self.invocation.testingargument}\nTesting option: {self.invocation.testingoption}" # fmt: skip
        await self.responder.respond(msg) # fmt: skip
        logging.info(msg)


class CommandCallerTestArg(CommandCallerBase[CommandInvocationTestArg]):
    def __init__(
        self,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
    ) -> None:
        super().__init__(
            locking_component=locking_component, permission_info=permission_info
        )

    def make_invocation(
        self, testingargument: str, testingoption: str
    ) -> tuple["CommandCallerTestArg", CommandInvocationTestArg]:
        return (
            self,
            CommandInvocationTestArg(
                testingargument=testingargument, testingoption=testingoption
            ),
        )

    def make_call(
        self, invocation: CommandInvocationTestArg, responder: IResponder
    ) -> CommandCallTestArg:
        return CommandCallTestArg(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
        )


def setup_cmd_testarg(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
) -> None:
    caller: CommandCallerTestArg = CommandCallerTestArg(
        locking_component=locking_component,
        permission_info=permission_info,
    )

    params: list[click.Parameter] = [
        click.Argument(["testingargument"], type=str, required=True),
        click.Option(
            ["-to", "--testingoption"],
            type=str,
            required=False,
            default="Default testingoption value",
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
