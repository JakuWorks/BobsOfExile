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

NAME: str = "testpowerdeviceconnection"


def setup_cmd_testpowerdeviceconnection(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_everyone_permission_info()

    callback = click.pass_context(call_cmd_testpowerdeviceconnection)
    command: click.Command = click.Command(
        name=NAME, callback=callback, add_help_option=False
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )


async def call_cmd_testpowerdeviceconnection_raw(call_context: CallContext) -> None:
    if call_context.grand.client_power_controller is None:
        await respond(call_context, "No power controller")
        return
    connected: bool = await call_context.grand.client_power_controller.test_device()
    await respond(call_context, f"Connected: {connected}")
    logging.info(f"Tested device connection ({connected=})")


async def call_cmd_testpowerdeviceconnection(ctx: click.Context, /) -> None: ...


call_cmd_testpowerdeviceconnection = simple_wrap_command_call(
    call_cmd_testpowerdeviceconnection_raw, respect_lock=False
)
