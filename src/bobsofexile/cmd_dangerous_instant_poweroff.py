from typing import AsyncIterable

import asyncclick as click

from .hardcoded import (
    POWEROFF_RETRIES,
    POWEROFF_RETRY_INTERVAL,
    NETCODE_REQUEST_PING,
    INSTANT_POWEROFF_PING_TIMEOUT,
)

from .calls_convenience import simple_wrap_command_call
from .commands import CommandsRegistry, CallContext
from .permissions import PermissionInfo
from .ranks import RanksRegistry
from .cmd_convenience import (
    simple_setup_cmd,
)
from .discord_convenience import respond_text_or_file_from_call_context as respond
from .networking import NetworkingMessage
from .main_convenience import get_future_time
from .discord_streaming_message import DiscordStreamingMessage

NAME: str = "dangerous_instant_poweroff"


def setup_cmd_dangerous_instant_poweroff(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_trusted_permission_info()

    callback = click.pass_context(call_cmd_dangerous_instant_poweroff)
    params: list[click.Parameter] = [
        click.Argument(["ignore_ping"], type=bool, required=False, default=False)
    ]
    command: click.Command = click.Command(
        name=NAME, callback=callback, params=params, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )


async def call_cmd_dangerous_instant_poweroff_raw(
    call_context: CallContext, ignore_ping: bool
) -> None:
    if call_context.grand.client_power_controller is None:
        await respond(
            call_context, "Client power controller is missing. Cannot cut power."
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

    message: DiscordStreamingMessage = DiscordStreamingMessage(
        initial_content=msg_begin, command_context=call_context.young.message_context
    )
    await message.start()

    if not ignore_ping:
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
            await call_context.grand.networking_handler.request(request_ping_msg)
        )
        if response is not None:
            await message.add_line(msg_ping_got)
            return
        await message.add_line(msg_ping_miss)

    poweroff_retrier: AsyncIterable[int] = (
        call_context.grand.client_power_controller.power_off_async_with_retries(
            retries=POWEROFF_RETRIES, interval=POWEROFF_RETRY_INTERVAL
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


async def call_cmd_dangerous_instant_poweroff(
    ctx: click.Context, /, ignore_ping: bool
) -> None: ...


call_cmd_dangerous_instant_poweroff = simple_wrap_command_call(
    call_cmd_dangerous_instant_poweroff_raw, respect_lock=True
)
