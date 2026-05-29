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

from .hardcoded import (
    NETCODE_REQUEST_POWER_DEVICE_STATUS,
    NETCODE_REPLY_POWER_DEVICE_STATUS_NO,
    NETCODE_REPLY_POWER_DEVICE_STATUS_OK,
    POWER_DEVICE_STATUS_REQUEST_TIMEOUT,
)
from .networking_framework import NetworkingMessage, NetworkingHandler
from .main_convenience import get_future_time

NAME: str = "testpowerdeviceconnectionrequest"


@dataclass(frozen=True, slots=True)
class CommandInvocationTestPowerDeviceConnectionRequest:
    pass


class CommandCallTestPowerDeviceConnectionRequest(
    CommandCallBase[CommandInvocationTestPowerDeviceConnectionRequest]
):
    networking_handler: NetworkingHandler

    def __init__(
        self,
        invocation: CommandInvocationTestPowerDeviceConnectionRequest,
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
        await self.responder.respond("Trying")
        msg_request: NetworkingMessage = NetworkingMessage(
            code=NETCODE_REQUEST_POWER_DEVICE_STATUS,
            id=None,
            is_reply=False,
            expiration=get_future_time(POWER_DEVICE_STATUS_REQUEST_TIMEOUT),
        )
        reply: NetworkingMessage | None = await self.networking_handler.request(
            msg=msg_request
        )
        if reply is None:
            await self.responder.respond("Timed out")
            return
        if reply.code == NETCODE_REPLY_POWER_DEVICE_STATUS_OK:
            await self.responder.respond(f"Got: OK ({reply.code})")
            return
        if reply.code == NETCODE_REPLY_POWER_DEVICE_STATUS_NO:
            await self.responder.respond(f"Got: NO ({reply.code})")
            return
        await self.responder.respond(f"Got unknown code ({reply.code})")


class CommandCallerTestPowerDeviceConnectionRequest(
    CommandCallerBase[CommandInvocationTestPowerDeviceConnectionRequest]
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
        self,
    ) -> tuple[
        "CommandCallerTestPowerDeviceConnectionRequest",
        CommandInvocationTestPowerDeviceConnectionRequest,
    ]:
        return (self, CommandInvocationTestPowerDeviceConnectionRequest())

    def make_call(
        self,
        invocation: CommandInvocationTestPowerDeviceConnectionRequest,
        responder: IResponder,
    ) -> CommandCallTestPowerDeviceConnectionRequest:
        return CommandCallTestPowerDeviceConnectionRequest(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            networking_handler=self.networking_handler,
        )


def setup_cmd_testpowerdeviceconnectionrequest(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
    networking_handler: NetworkingHandler,
) -> None:
    caller: CommandCallerTestPowerDeviceConnectionRequest = (
        CommandCallerTestPowerDeviceConnectionRequest(
            locking_component=locking_component,
            permission_info=permission_info,
            networking_handler=networking_handler,
        )
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
