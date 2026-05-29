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

NAME: str = "testerror"


@dataclass(frozen=True, slots=True)
class CommandInvocationTestError:
    pass


class CommandCallTestError(CommandCallBase[CommandInvocationTestError]):
    def __init__(
        self,
        invocation: CommandInvocationTestError,
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
        await self.responder.respond("Msg before error")
        logging.info("Error test before")

        class SomeTestingError(Exception):
            pass

        raise SomeTestingError("Error test")

        assert False, "Unreachable code"
        await respond(call_context, "Msg after error")
        logging.info("Error test after")


class CommandCallerTestError(CommandCallerBase[CommandInvocationTestError]):
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
    ) -> tuple["CommandCallerTestError", CommandInvocationTestError]:
        return (self, CommandInvocationTestError())

    def make_call(
        self, invocation: CommandInvocationTestError, responder: IResponder
    ) -> CommandCallTestError:
        return CommandCallTestError(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
        )


def setup_cmd_testerror(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
) -> None:
    caller: CommandCallerTestError = CommandCallerTestError(
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
