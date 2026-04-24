import logging

import asyncclick as click

from .calls_convenience import simple_wrap_command_call
from .commands import CommandsRegistry, CallContext
from .permissions import PermissionInfo
from .ranks import RanksRegistry
from .cmd_convenience import (
    simple_setup_cmd,
)
from .networking import NetworkingMessage
from .discord_streaming_message import DiscordStreamingMessage

NAME: str = "debug_sendnetrequest"


def setup_cmd_debug_sendnetrequest(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_owner_permission_info()

    callback = click.pass_context(call_cmd_debug_sendnetrequest)
    params: list[click.Parameter] = [
        click.Argument(["code"], type=int, required=True),
        click.Argument(["timeout"], type=int, required=False, default=10),
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


async def call_cmd_debug_sendnetrequest_raw(
    call_context: CallContext, code: int, timeout: int
) -> None:
    logging.info(f"Sending debug net request with code {code=} {timeout=}")
    msg: NetworkingMessage = NetworkingMessage(code=code, is_reply=False, id=None)
    streaming_message: DiscordStreamingMessage = DiscordStreamingMessage(
        initial_content=f"Requesting with code {msg.code=} {msg.is_reply=} {msg.id=} and will time out in {timeout=}",
        command_context=call_context.young.message_context,
    )
    await streaming_message.start()
    response: NetworkingMessage | None = (
        await call_context.grand.networking_handler.request(msg=msg, timeout=timeout)
    )
    if response is None:
        logging.info("Debug net request got no response")
        await streaming_message.add_line("Timed out without a response")
    else:
        logging.info(f"Debug net request got response with code {response.code}")
        await streaming_message.add_line(
            f"Got response with {response.code=} {response.is_reply=} {response.id=}"
        )


async def call_cmd_debug_sendnetrequest(
    ctx: click.Context, /, code: int, timeout: int
) -> None: ...


call_cmd_debug_sendnetrequest = simple_wrap_command_call(
    call_cmd_debug_sendnetrequest_raw, respect_lock=False
)
