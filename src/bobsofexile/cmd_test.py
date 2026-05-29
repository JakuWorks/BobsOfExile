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

NAME: str = "test"


@dataclass(frozen=True, slots=True)
class CommandInvocationTest:
    pass


class CommandCallTest(CommandCallBase[CommandInvocationTest]):
    def __init__(
        self,
        invocation: CommandInvocationTest,
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
        await self.responder.respond("Testing hello!")
        logging.info("Test")


class CommandCallerTest(CommandCallerBase[CommandInvocationTest]):
    def __init__(
        self,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
    ) -> None:
        super().__init__(
            locking_component=locking_component, permission_info=permission_info
        )

    def make_invocation(self) -> tuple["CommandCallerTest", CommandInvocationTest]:
        return (self, CommandInvocationTest())

    def make_call(
        self, invocation: CommandInvocationTest, responder: IResponder
    ) -> CommandCallTest:
        return CommandCallTest(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
        )


def setup_cmd_test(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
) -> None:
    caller: CommandCallerTest = CommandCallerTest(
        locking_component=locking_component,
        permission_info=permission_info,
    )

    command: click.Command = click.Command(
        name=NAME,
        callback=caller.make_invocation,
        add_help_option=False,
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
    )
