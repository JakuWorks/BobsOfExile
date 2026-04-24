import logging
from typing import assert_never

import asyncclick as click

from .calls_convenience import simple_wrap_command_call
from .commands import CommandsRegistry, CallContext
from .permissions import PermissionInfo
from .ranks import RanksRegistry
from .cmd_convenience import (
    simple_setup_cmd,
)
from .discord_convenience import respond_text_or_file_from_call_context as respond

NAME: str = "testerror"


def setup_cmd_testerror(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_everyone_permission_info()

    callback = click.pass_context(call_cmd_testerror)
    command: click.Command = click.Command(
        name=NAME, callback=callback, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )


async def call_cmd_testerror_raw(call_context: CallContext) -> None:
    await respond(call_context, "Msg before error")
    logging.info("Error test before")

    class SomeTestingError(Exception):
        pass

    raise SomeTestingError("Error test")

    assert_never()
    await respond(call_context, "Msg after error")
    logging.info("Error test after")


async def call_cmd_testerror(ctx: click.Context, /) -> None: ...


call_cmd_testerror = simple_wrap_command_call(call_cmd_testerror_raw, respect_lock=False)
