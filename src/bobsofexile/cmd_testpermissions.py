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

NAME: str = "testpermissions"


def setup_cmd_testpermissions(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_no_one_permission_info()

    callback = click.pass_context(call_cmd_testpermissions)
    command: click.Command = click.Command(
        name=NAME, callback=callback, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )


async def call_cmd_testpermissions_raw(call_context: CallContext) -> None:
    await respond(call_context, "skibidi 67 67")
    logging.info("permission test")


async def call_cmd_testpermissions(ctx: click.Context, /) -> None: ...


call_cmd_testpermissions = simple_wrap_command_call(call_cmd_testpermissions_raw, respect_lock=False)
