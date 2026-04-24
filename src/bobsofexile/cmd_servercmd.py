import asyncclick as click

from .calls_convenience import simple_wrap_command_call
from .commands import CommandsRegistry, CallContext
from .permissions import PermissionInfo
from .ranks import RanksRegistry
from .cmd_convenience import (
    simple_setup_cmd,
)
from .discord_convenience import respond_text_or_file_from_call_context as respond

NAME: str = "servercmd"


def setup_cmd_servercmd(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_trusted_permission_info()

    callback = click.pass_context(call_cmd_servercmd)
    params: list[click.Parameter] = [
        click.Argument(["server_command"], type=str, required=True),
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


async def call_cmd_servercmd_raw(
    call_context: CallContext, server_command: str
) -> None:
    if call_context.grand.server_instance is None:
        await respond(call_context, "Server was never started")
        return

    if not call_context.grand.server_instance.running:
        await respond(call_context, "Server is not running")

    call_context.grand.server_instance.send_command(text=server_command)
    await respond(call_context, "Sent command")


async def call_cmd_servercmd(ctx: click.Context, /, server_command: str) -> None: ...


call_cmd_servercmd = simple_wrap_command_call(call_cmd_servercmd_raw, respect_lock=True)
