import asyncclick as click

from .calls_convenience import simple_wrap_command_call
from .commands import CommandsRegistry, CallContext
from .permissions import PermissionInfo
from .ranks import RanksRegistry
from .cmd_convenience import (
    simple_setup_cmd,
)
from .discord_convenience import respond_text_or_file_from_call_context as respond

NAME: str = "help"


def setup_cmd_help(
    commands_registry: CommandsRegistry, ranks_registry: RanksRegistry
) -> None:
    permission_info: PermissionInfo = ranks_registry.get_everyone_permission_info()

    callback = click.pass_context(call_cmd_help)
    params: list[click.Parameter] = [
        click.Argument(["cmd_or_empty"], type=str, required=False, default=None)
    ]
    command: click.Command = click.Command(
        name=NAME, callback=callback, add_help_option=False, params=params
    )

    simple_setup_cmd(
        name=NAME,
        click_command=command,
        commands_registry=commands_registry,
        permission_info=permission_info,
    )


async def call_cmd_help_raw(
    call_context: CallContext, cmd_or_empty: str | None
) -> None:
    if cmd_or_empty is not None:
        cmd_help: str | None = call_context.grand.commands_registry.get_command_help(
            command=cmd_or_empty
        )
        if cmd_help is None:
            await respond(call_context, "No command found")
        else:
            await respond(call_context, cmd_help)
    else:
        await respond(call_context, call_context.grand.commands_registry.get_all_help())


async def call_cmd_help(ctx: click.Context, /, cmd_or_empty: str | None) -> None: ...


call_cmd_help = simple_wrap_command_call(call_cmd_help_raw, respect_lock=False)
