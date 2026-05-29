from dataclasses import dataclass
import logging
import asyncio

import asyncclick as click

from .commands import (
    simple_setup_cmd,
    ILockingComponent,
    CommandsRegistry,
    CommandCallBase,
    CommandCallerBase,
)
from .responder import IResponder, ILongResponse
from .permission_info import IPermissionInfo

NAME: str = "teststream"


@dataclass(frozen=True, slots=True)
class CommandInvocationTestStream:
    pass


class CommandCallTestStream(CommandCallBase[CommandInvocationTestStream]):
    def __init__(
        self,
        invocation: CommandInvocationTestStream,
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
        message: ILongResponse = self.responder.new_long_response(
            init_msg="initial content",
        )
        await message.start()
        for i in range(3):
            await message.add_line(f"edit {i}")
            await asyncio.sleep(0.5)
        logging.info("Streamtest")


class CommandCallerTestStream(CommandCallerBase[CommandInvocationTestStream]):
    def __init__(
        self,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
    ) -> None:
        super().__init__(
            locking_component=locking_component, permission_info=permission_info
        )

    def make_invocation(
        self,
    ) -> tuple["CommandCallerTestStream", CommandInvocationTestStream]:
        return (self, CommandInvocationTestStream())

    def make_call(
        self, invocation: CommandInvocationTestStream, responder: IResponder
    ) -> CommandCallTestStream:
        return CommandCallTestStream(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
        )


def setup_cmd_teststream(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
) -> None:
    caller: CommandCallerTestStream = CommandCallerTestStream(
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
