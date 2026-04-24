import logging

import asyncclick as click

from .calls_convenience import simple_wrap_command_call
from .commands import CommandsRegistry, CallContext
from .permissions import PermissionInfo
from .ranks import RanksRegistry
from .cmd_convenience import (
    simple_setup_cmd,
)
from .discord_convenience import respond_text_or_file_from_call_context as respond

NAME: str = "testarg"


def setup_cmd_testarg(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_everyone_permission_info()

    callback = click.pass_context(call_cmd_testarg)
    params: list[click.Parameter] = [
        click.Argument(["testingargument"], type=str, required=True)
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


async def call_cmd_testarg_raw(call_context: CallContext, testingargument: str) -> None:
    await respond(call_context, f"skibidi, {testingargument}")
    logging.info(f"Arg Test {testingargument}")


async def call_cmd_testarg(ctx: click.Context, /, testingargument: str) -> None: ...


call_cmd_testarg = simple_wrap_command_call(call_cmd_testarg_raw, respect_lock=False)
