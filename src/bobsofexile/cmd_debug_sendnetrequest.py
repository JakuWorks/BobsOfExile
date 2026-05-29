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
from .responder import IResponder, ILongResponse
from .permission_info import IPermissionInfo

from .main_convenience import get_future_time
from .networking_framework import NetworkingHandler, NetworkingMessage

NAME: str = "debug_sendnetrequest"


@dataclass(frozen=True, slots=True)
class CommandInvocationDebugSendNetRequest:
    code: int
    timeout: int


class CommandCallDebugSendNetRequest(
    CommandCallBase[CommandInvocationDebugSendNetRequest]
):
    networking_handler: NetworkingHandler

    def __init__(
        self,
        invocation: CommandInvocationDebugSendNetRequest,
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
        logging.info(
            f"Sending debug net request with code {self.invocation.code=} {self.invocation.timeout=}"
        )
        msg: NetworkingMessage = NetworkingMessage(
            code=self.invocation.code,
            is_reply=False,
            id=None,
            expiration=get_future_time(self.invocation.timeout),
        )

        message: ILongResponse = self.responder.new_long_response(
            init_msg=f"Requesting with code {msg.code=} {msg.is_reply=} {msg.id=} and will time out in {self.invocation.timeout=}",
        )
        await message.start()
        response: NetworkingMessage | None = await self.networking_handler.request(
            msg=msg
        )
        if response is None:
            logging.info("Debug net request got no response")
            await message.add_line("Timed out without a response")
        else:
            logging.info(f"Debug net request got response with code {response.code}")
            await message.add_line(
                f"Got response with {response.code=} {response.is_reply=} {response.id=}"
            )


class CommandCallerDebugSendNetRequest(
    CommandCallerBase[CommandInvocationDebugSendNetRequest]
):
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
        self, code: int, timeout: int
    ) -> tuple[
        "CommandCallerDebugSendNetRequest", CommandInvocationDebugSendNetRequest
    ]:
        return (self, CommandInvocationDebugSendNetRequest(code=code, timeout=timeout))

    def make_call(
        self, invocation: CommandInvocationDebugSendNetRequest, responder: IResponder
    ) -> CommandCallDebugSendNetRequest:
        return CommandCallDebugSendNetRequest(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            networking_handler=self.networking_handler,
        )


def setup_cmd_debug_sendnetrequest(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
    networking_handler: NetworkingHandler,
) -> None:
    caller: CommandCallerDebugSendNetRequest = CommandCallerDebugSendNetRequest(
        locking_component=locking_component,
        permission_info=permission_info,
        networking_handler=networking_handler,
    )

    params: list[click.Parameter] = [
        click.Argument(["code"], type=int, required=True),
        click.Argument(["timeout"], type=int, required=False, default=10),
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
