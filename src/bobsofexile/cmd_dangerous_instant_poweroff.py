from dataclasses import dataclass
from typing import AsyncIterable

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

from .hardcoded import (
    NETCODE_REQUEST_PING,
    INSTANT_POWEROFF_PING_TIMEOUT,
    REMOTE_POWEROFF_RETRIES,
    REMOTE_POWEROFF_RETRY_INTERVAL,
)
from .networking_framework import NetworkingMessage, NetworkingHandler
from .main_convenience import get_future_time
from .power_device import IPowerController

NAME: str = "dangerous_instant_poweroff"


@dataclass(frozen=True, slots=True)
class CommandInvocationDangerousInstantPoweroff:
    ignore_ping: bool


class CommandCallDangerousInstantPoweroff(
    CommandCallBase[CommandInvocationDangerousInstantPoweroff]
):
    client_power_controller: IPowerController
    networking_handler: NetworkingHandler

    def __init__(
        self,
        invocation: CommandInvocationDangerousInstantPoweroff,
        responder: IResponder,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        client_power_controller: IPowerController,
        networking_handler: NetworkingHandler,
    ) -> None:
        super().__init__(
            invocation=invocation,
            responder=responder,
            locking_component=locking_component,
            permission_info=permission_info,
        )
        self.client_power_controller = client_power_controller
        self.networking_handler = networking_handler

    async def call(self) -> None:
        msg_begin: str = "Instant poweroff results:"
        msg_ping_request_format: str = (
            "Requesting a pong from client with a timeout of {0} seconds..."
        )
        msg_ping_got: str = (
            "Got a pong! The client is certainly running. This command WILL NOT cut the power."
        )
        msg_ping_miss: str = (
            "Timed out: the client is likely off. The power cut WILL BE attempted..."
            '("likely" because network errors may happen sometimes)'
        )

        message: ILongResponse = self.responder.new_long_response(init_msg=msg_begin)
        await message.start()

        if not self.invocation.ignore_ping:
            request_ping_msg: NetworkingMessage = NetworkingMessage(
                code=NETCODE_REQUEST_PING,
                is_reply=False,
                expiration=get_future_time(after_seconds=INSTANT_POWEROFF_PING_TIMEOUT),
                id=None,
            )
            await message.add_line(
                msg_ping_request_format.format(INSTANT_POWEROFF_PING_TIMEOUT)
            )
            response: NetworkingMessage | None = await self.networking_handler.request(
                request_ping_msg
            )
            if response is not None:
                await message.add_line(msg_ping_got)
                return
            await message.add_line(msg_ping_miss)

        poweroff_retrier: AsyncIterable[int] = (
            self.client_power_controller.power_off_async_with_retries(
                retries=REMOTE_POWEROFF_RETRIES, interval=REMOTE_POWEROFF_RETRY_INTERVAL
            )
        )
        success_final: bool = False
        async for success in poweroff_retrier:
            if success:
                await message.add_line("Poweroff attempt: success")
                success_final = True
                break
            await message.add_line("Poweroff attempt: failure")
        if success_final:
            await message.add_line("Final: Success")
        else:
            await message.add_line("Final: Failure")


class CommandCallerDangerousInstantPoweroff(
    CommandCallerBase[CommandInvocationDangerousInstantPoweroff]
):
    client_power_controller: IPowerController
    networking_handler: NetworkingHandler

    def __init__(
        self,
        locking_component: ILockingComponent,
        permission_info: IPermissionInfo,
        client_power_controller: IPowerController,
        networking_handler: NetworkingHandler,
    ) -> None:
        super().__init__(
            locking_component=locking_component, permission_info=permission_info
        )
        self.client_power_controller = client_power_controller
        self.networking_handler = networking_handler

    def make_invocation(self, ignore_ping: bool) -> tuple[
        "CommandCallerDangerousInstantPoweroff",
        CommandInvocationDangerousInstantPoweroff,
    ]:
        return (
            self,
            CommandInvocationDangerousInstantPoweroff(ignore_ping=ignore_ping),
        )

    def make_call(
        self,
        invocation: CommandInvocationDangerousInstantPoweroff,
        responder: IResponder,
    ) -> CommandCallDangerousInstantPoweroff:
        return CommandCallDangerousInstantPoweroff(
            invocation=invocation,
            responder=responder,
            locking_component=self.locking_component,
            permission_info=self.permission_info,
            client_power_controller=self.client_power_controller,
            networking_handler=self.networking_handler,
        )


def setup_cmd_dangerous_instant_poweroff(
    commands_registry: CommandsRegistry,
    locking_component: ILockingComponent,
    permission_info: IPermissionInfo,
    client_power_controller: IPowerController,
    networking_handler: NetworkingHandler,
) -> None:
    caller: CommandCallerDangerousInstantPoweroff = (
        CommandCallerDangerousInstantPoweroff(
            locking_component=locking_component,
            permission_info=permission_info,
            client_power_controller=client_power_controller,
            networking_handler=networking_handler,
        )
    )

    params: list[click.Parameter] = [
        click.Argument(["ignore_ping"], type=bool, required=False, default=False)
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
