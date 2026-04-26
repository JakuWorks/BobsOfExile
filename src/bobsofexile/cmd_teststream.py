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
from .discord_streaming_message import DiscordStreamingMessage

NAME: str = "teststream"


def setup_cmd_teststream(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_everyone_permission_info()

    callback = click.pass_context(call_cmd_teststream)
    command: click.Command = click.Command(
        name=NAME, callback=callback, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )


async def call_cmd_teststream_raw(call_context: CallContext) -> None:
    msg: DiscordStreamingMessage = DiscordStreamingMessage(
        initial_content="initial content",
        command_context=call_context.young.message_context,
    )
    await msg.start()
    for i in range(3):
        await msg.add_line(f"edit {i}")
        await asyncio.sleep(0.5)
    logging.info("Streamtest")


async def call_cmd_teststream(ctx: click.Context, /) -> None: ...


call_cmd_teststream = simple_wrap_command_call(
    call_cmd_teststream_raw, respect_lock=False
)
