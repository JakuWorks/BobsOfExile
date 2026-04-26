import logging
import asyncio

import asyncclick as click

from .calls_convenience import simple_wrap_command_call
from .commands import CommandsRegistry, CallContext
from .permissions import PermissionInfo
from .ranks import RanksRegistry
from .cmd_convenience import (
    simple_setup_cmd,
)
from .networking import NetworkingMessage, RequestReplyContext, RequestReplyContextYoung
from .discord_streaming_message import DiscordStreamingMessage
from .main_convenience import get_future_time

NAME: str = "debug_setupsimplenetcodereplier"


def setup_cmd_debug_setupsimplenetcodereplier(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_owner_permission_info()

    callback = click.pass_context(call_cmd_debug_setupsimplenetcodereplier)
    params: list[click.Parameter] = [
        click.Argument(["listencode"], type=int, required=True),
        click.Argument(["replycode"], type=int, required=True),
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


async def call_cmd_debug_setupsimplenetcodereplier_raw(
    call_context: CallContext, listencode: int, replycode: int, timeout: int
) -> None:
    logging.info(
        f"Setting up a temporary debug net code replier {listencode=} {replycode=} {timeout=}"
    )

    streaming_message: DiscordStreamingMessage = DiscordStreamingMessage(
        initial_content=f"Setting up a temporary debug simple net code replier {listencode=} {replycode=} that will be removed after {timeout=}",
        command_context=call_context.young.message_context,
    )
    await streaming_message.start()

    async def reply_hook(request_reply_context: RequestReplyContext) -> None:
        received_msg: NetworkingMessage = request_reply_context.youngest.msg
        reply_msg: NetworkingMessage = NetworkingMessage(
            code=replycode, id=received_msg.id, is_reply=True, expiration=get_future_time(timeout)
        )

        await streaming_message.add_line(
            f"\nGot msg with {received_msg.code=} {received_msg.is_reply=} {received_msg.id=}"
            f"\nReplying to it with {reply_msg.code=} {reply_msg.is_reply=} {reply_msg.id=} "
        )
        await request_reply_context.young.networking_handler.reply(reply_msg)

    request_reply_context_young: RequestReplyContextYoung = RequestReplyContextYoung(
        networking_handler=call_context.grand.networking_handler
    )
    call_context.grand.networking_handler.request_replier.add_hook(
        code=listencode, hook=reply_hook, once=False, ctx=request_reply_context_young
    )

    await asyncio.sleep(timeout)

    call_context.grand.networking_handler.request_replier.remove_hook(code=listencode)
    await streaming_message.add_line(
        "\nRemoved the simple net code replier hook (time out)"
    )


async def call_cmd_debug_setupsimplenetcodereplier(
    ctx: click.Context, /, listencode: int, replycode: int, timeout: int
) -> None: ...


call_cmd_debug_setupsimplenetcodereplier = simple_wrap_command_call(
    call_cmd_debug_setupsimplenetcodereplier_raw, respect_lock=False
)
