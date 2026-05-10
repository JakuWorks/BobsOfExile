from typing import AsyncIterable

import asyncclick as click

from .hardcoded import (
    REMOTE_POWEROFF_RETRIES,
    REMOTE_POWEROFF_RETRY_INTERVAL,
    NETCODE_REQUEST_PING,
    INSTANT_POWEROFF_PING_TIMEOUT,
)
from .networking import NetworkingMessage
from .main_convenience import get_future_time
from .commands import (
    simple_setup_cmd,
    ICommandCall,
    ICommandInvocationStandard,
    CallContextGrand,
    CommandsRegistry,
)
from .responder import IResponder, ILongResponse
from .permissions import IPermissionInfo
from .ranks import RanksRegistry

NAME: str = "dangerous_instant_poweroff"


class CommandCallDangerousInstantPoweroff(ICommandCall):
    __slots__ = (
        "responder",
        "call_context_grand",
        "ignore_ping",
    )

    responder: IResponder
    call_context_grand: CallContextGrand

    ignore_ping: bool

    def __init__(
        self,
        responder: IResponder,
        call_context_grand: CallContextGrand,
        ignore_ping: bool,
    ) -> None:
        self.responder = responder
        self.call_context_grand = call_context_grand

        self.ignore_ping = ignore_ping

    async def call(self) -> None:
        if self.call_context_grand.client_power_controller is None:
            await self.responder.respond(
                "Client power controller is missing. Cannot cut power."
            )
            return

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

        if not self.ignore_ping:
            request_ping_msg: NetworkingMessage = NetworkingMessage(
                code=NETCODE_REQUEST_PING,
                is_reply=False,
                expiration=get_future_time(after_seconds=INSTANT_POWEROFF_PING_TIMEOUT),
                id=None,
            )
            await message.add_line(
                msg_ping_request_format.format(INSTANT_POWEROFF_PING_TIMEOUT)
            )
            response: NetworkingMessage | None = (
                await self.call_context_grand.networking_handler.request(
                    request_ping_msg
                )
            )
            if response is not None:
                await message.add_line(msg_ping_got)
                return
            await message.add_line(msg_ping_miss)

        poweroff_retrier: AsyncIterable[int] = (
            self.call_context_grand.client_power_controller.power_off_async_with_retries(
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


class CommandInvocationDangerousInstantPoweroff(ICommandInvocationStandard):
    __slots__ = ("ignore_ping",)

    ignore_ping: bool

    def __init__(self, ignore_ping: bool) -> None:
        self.ignore_ping = ignore_ping

    def make_call(
        self, responder: IResponder, call_context_grand: CallContextGrand
    ) -> CommandCallDangerousInstantPoweroff:
        return CommandCallDangerousInstantPoweroff(
            responder=responder,
            call_context_grand=call_context_grand,
            ignore_ping=self.ignore_ping,
        )

    def get_default_respect_locks(self) -> bool:
        return True


def invoke_dangerous_instant_poweroff(
    ignore_ping: bool,
) -> CommandInvocationDangerousInstantPoweroff:
    return CommandInvocationDangerousInstantPoweroff(ignore_ping=ignore_ping)


def setup_cmd_dangerous_instant_poweroff(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: IPermissionInfo = ranks_registry.get_trusted_permission_info()

    params: list[click.Parameter] = [
        click.Argument(["ignore_ping"], type=bool, required=False, default=False)
    ]
    command: click.Command = click.Command(
        name=NAME,
        callback=invoke_dangerous_instant_poweroff,
        add_help_option=False,
        params=params,
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )
