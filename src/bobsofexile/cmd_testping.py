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

from .main_convenience import get_future_time
from .hardcoded import NETCODE_REQUEST_PING, TESTPING_TIMEOUT
from .networking_framework import NetworkingMessage, NetworkingHandler

NAME: str = "testping"


@dataclass(frozen=True, slots=True)
class CommandInvocationTestPing:
    pass


class CommandCallTestPing(CommandCallBase[CommandInvocationTestPing]):
    networking_handler: NetworkingHandler

    def __init__(
        self,
        invocation: CommandInvocationTestPing,
        responder: IResponder,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        networking_handler: NetworkingHandler,
    ) -> None:
        super().__init__(
            invocation=invocation,
            responder=responder,
            locking_component=locking_component,
            permission_info=permission_info,
        )
        self.networking_handler = networking_handler

    async def call(self) -> None:
        request_ping_msg: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REQUEST_PING,
            is_reply=False,
            expiration=get_future_time(after_seconds=TESTPING_TIMEOUT),
            id=None,
        )
        response: NetworkingMessage | None = await self.networking_handler.request(
            request_ping_msg
        )
        if response:
            await self.responder.respond("Pong!")
        else:
            await self.responder.respond("Timed out.")


class CommandCallerTestPing(CommandCallerBase[CommandInvocationTestPing]):
    networking_handler: NetworkingHandler

    def __init__(
        self,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        networking_handler: NetworkingHandler,
    ) -> None:
        super().__init__(
            locking_component=locking_component, permission_info=permission_info
        )
        self.networking_handler = networking_handler

    def make_invocation(
        self,
    ) -> tuple["CommandCallerTestPing", CommandInvocationTestPing]:
        return (self, CommandInvocationTestPing())

    def make_call(
        self, invocation: CommandInvocationTestPing, responder: IResponder
    ) -> CommandCallTestPing:
        return CommandCallTestPing(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            networking_handler=self.networking_handler,
        )


def setup_cmd_testping(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
    networking_handler: NetworkingHandler,
) -> None:
    caller: CommandCallerTestPing = CommandCallerTestPing(
        locking_component=locking_component,
        permission_info=permission_info,
        networking_handler=networking_handler,
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
