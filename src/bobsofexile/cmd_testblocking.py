import logging
import asyncio
import random

import asyncclick as click

from .calls_convenience import simple_wrap_command_call
from .commands import CommandsRegistry, CallContext
from .permissions import PermissionInfo
from .ranks import RanksRegistry
from .cmd_convenience import (
    simple_setup_cmd,
)
from .discord_convenience import respond_text_or_file_from_call_context as respond

NAME: str = "testblocking"


def setup_cmd_testblocking(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_everyone_permission_info()

    callback = click.pass_context(call_cmd_testblocking)
    command: click.Command = click.Command(
        name=NAME, callback=callback, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )


async def call_cmd_testblocking_raw(call_context: CallContext) -> None:
    t: int = 5
    random_id: int = random.randint(1, 99)
    await respond(call_context, f"Blocking {t=} ({random_id})")
    logging.info(f"Blocking {t=} ({random_id})")
    await asyncio.sleep(t)
    await respond(call_context, f"Finished blocking ({random_id})")
    logging.info(f"Finished blocking ({random_id})")


async def call_cmd_testblocking(ctx: click.Context, /) -> None: ...


call_cmd_testblocking = simple_wrap_command_call(call_cmd_testblocking_raw, respect_lock=True)
