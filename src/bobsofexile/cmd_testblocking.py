from dataclasses import dataclass
import logging
import asyncio
import random

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

NAME: str = "testblocking"


@dataclass(frozen=True, slots=True)
class CommandInvocationTestBlocking:
    pass


class CommandCallTestBlocking(CommandCallBase[CommandInvocationTestBlocking]):
    def __init__(
        self,
        invocation: CommandInvocationTestBlocking,
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
        t: int = 5
        random_id: int = random.randint(1, 99)
        msg_blocking: str = f"Blocking {t=} {random_id}"
        msg_finished: str = f"Finished blocking {random_id}"

        await self.responder.respond(msg_blocking)
        logging.info(msg_blocking)

        await asyncio.sleep(t)
        await self.responder.respond(msg_finished)
        logging.info(msg_finished)


class CommandCallerTestBlocking(CommandCallerBase[CommandInvocationTestBlocking]):
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
    ) -> tuple["CommandCallerTestBlocking", CommandInvocationTestBlocking]:
        return (self, CommandInvocationTestBlocking())

    def make_call(
        self, invocation: CommandInvocationTestBlocking, responder: IResponder
    ) -> CommandCallTestBlocking:
        return CommandCallTestBlocking(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
        )


def setup_cmd_testblocking(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
) -> None:
    caller: CommandCallerTestBlocking = CommandCallerTestBlocking(
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
